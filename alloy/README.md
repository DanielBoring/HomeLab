# Grafana Alloy

Grafana Alloy is a vendor-neutral OpenTelemetry collector and observability pipeline. It replaces Promtail in this stack and extends it with syslog ingestion for network devices and an OTLP endpoint for any service that speaks OpenTelemetry.

[https://grafana.com/docs/alloy/latest/](https://grafana.com/docs/alloy/latest/)

## What it collects

| Source | How | Destination |
|---|---|---|
| Docker container logs | Docker socket (auto-discovery) | Loki |
| TrueNAS systemd journal | `/var/log/journal` mount | Loki |
| Syslog (UniFi, TrueNAS, etc.) | UDP/TCP push to `:514` | Loki |
| OTLP logs | gRPC `:4317` / HTTP `:4318` | Loki |
| OTLP metrics | gRPC `:4317` / HTTP `:4318` | Prometheus (remote write) |
| OTLP traces | `:4317` / `:4318` | dropped — add Tempo to enable |

## Architecture

```
Docker socket ──────────────────────────────────┐
/var/log/journal ────────────────────────────── Alloy ──→ Loki
Network devices (UDP/TCP :514) ─────────────────┤
OTLP apps (gRPC :4317 / HTTP :4318) ───logs ───┘
                                    └──metrics──→ Prometheus
                                    └──traces───→ (dropped)

Browser (HTTPS) → Traefik → Alloy :12345 (debug UI)
```

## Syslog port mapping

Alloy cannot bind privileged port 514 inside the container without root. Instead it listens on **5514** internally, and Docker maps host port `514 → 5514`. Network devices send to `TrueNAS_IP:514` as normal — the mapping is transparent to them.

## Prerequisites

### Host directories and config

```sh
mkdir -p /mnt/SSD/Containers/alloy
```

Copy `config.alloy` from this repo to TrueNAS before deploying — the container bind-mounts it from an absolute path, so it must exist on the host first:

```sh
scp alloy/config.alloy truenas:/mnt/SSD/Containers/alloy/config.alloy
```

Or paste the contents directly in a TrueNAS shell: `nano /mnt/SSD/Containers/alloy/config.alloy`

### Docker socket access

Alloy runs as the `alloy` user inside the container. It reads `/var/run/docker.sock` for container log discovery. If logs from Docker containers are not appearing, the socket permissions on the host may need adjustment:

```sh
# Check current permissions
ls -la /var/run/docker.sock

# If needed, add the alloy user's GID (473) to the docker group, or run:
chmod 666 /var/run/docker.sock
```

### DNS

Add a record for `alloy.yourdomain.com` → `10.0.5.5` (Traefik).

## Quick Start

```sh
# 1. Bring down the loki stack first (Promtail is being replaced)
cd loki && docker compose down

# 2. Start Alloy
cd alloy && docker compose up -d

# 3. Restart the loki stack (without Promtail)
cd loki && docker compose up -d

# 4. Restart Prometheus to pick up the remote-write-receiver flag and new scrape job
cd prometheus && docker compose up -d
```

Navigate to `https://alloy.yourdomain.com` for the debug UI. The **Graph** tab shows the live pipeline and whether each component is healthy.

## Configuring UniFi devices to send syslog

In UniFi Network → **Settings → System → Remote Logging**:

- **Syslog Host**: TrueNAS IP address
- **Syslog Port**: `514`

Each device (UDM SE, switches, APs, PDU) has its own remote logging setting. Repeat for each one. Logs will appear in Loki under `{job="syslog"}` with `host`, `level`, `facility`, and `app` labels.

## Configuring TrueNAS to send syslog

In TrueNAS → **System → Advanced → Syslog**:

- **Use FQDN for logging**: off (keeps hostnames short)
- **Syslog Level**: Informational
- **Syslog Server**: `TrueNAS_IP:514`
- **Syslog Transport**: UDP

## Sending OTLP from a service

Point your application's OTLP exporter at TrueNAS:

| Protocol | Endpoint |
|---|---|
| gRPC | `http://TrueNAS_IP:4317` |
| HTTP | `http://TrueNAS_IP:4318` |

For Docker services on the `monitoring` network, use the container name:

| Protocol | Endpoint |
|---|---|
| gRPC | `http://alloy:4317` |
| HTTP | `http://alloy:4318` |

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ALLOY_DOMAIN` | — | Public hostname for the Traefik debug UI |
| `OTLP_GRPC_PORT` | `4317` | Host port for OTLP gRPC |
| `OTLP_HTTP_PORT` | `4318` | Host port for OTLP HTTP |

## Adding trace storage (Tempo)

To stop dropping OTLP traces, deploy [Grafana Tempo](https://grafana.com/docs/tempo/latest/) and update `config.alloy`:

```alloy
otelcol.exporter.otlp "tempo" {
  client {
    endpoint = "tempo:4317"
    tls {
      insecure = true
    }
  }
}
```

Then wire `traces = [otelcol.exporter.otlp.tempo.input]` in the `otelcol.receiver.otlp` output block.
