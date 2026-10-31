# Grafana Alloy

Grafana Alloy is a vendor-neutral OpenTelemetry collector and observability pipeline. It replaces Promtail in this stack and extends it with syslog ingestion for network devices and an OTLP endpoint for any service that speaks OpenTelemetry.

[https://grafana.com/docs/alloy/latest/](https://grafana.com/docs/alloy/latest/)

Images in `compose.yaml` are frozen to the inventoried builds. See the [image update guide](../README.md#image-updates); `docker compose pull` alone does not upgrade them.

## What it collects

| Source | How | Destination |
|---|---|---|
| Docker container logs | Docker socket (auto-discovery) | Loki |
| TrueNAS systemd journal | `/var/log/journal` mount | Loki |
| Syslog (UniFi, TrueNAS, etc.) | UDP/TCP push to `:514` | Loki |
| OTLP logs | gRPC `:4317` / HTTP `:4318` | Loki |
| OTLP metrics | gRPC `:4317` / HTTP `:4318` | Prometheus (remote write) |
| OTLP traces | `:4317` / `:4318` | dropped — add Tempo to enable |
| Windows Event Logs | Alloy service on Windows | Loki |
| Windows host, AD, DNS, DFSR, service, and process metrics | Alloy service on Windows | Prometheus |

## Architecture

```text
Docker socket ──────────────────────────────────┐
/var/log/journal ────────────────────────────── Alloy ──→ Loki
Network devices (UDP/TCP :514) ─────────────────┤
OTLP apps (gRPC :4317 / HTTP :4318) ───logs ───┘
                                    └──metrics──→ Prometheus
                                    └──traces───→ (dropped)
Windows Alloy agents (remote write :9999) ─────→ Alloy ──→ Prometheus

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
The transfer example runs from the checkout root on the source machine;
host-directory preparation runs on Linux. Preserve an existing host config
before replacing it.

```sh
scp alloy/config.alloy truenas:/mnt/SSD/Containers/alloy/config.alloy
```

Or paste the contents directly in a TrueNAS shell: `nano /mnt/SSD/Containers/alloy/config.alloy`

### Docker socket access

Alloy reads `/var/run/docker.sock` for container log discovery. The Compose file does not override the image's user; verify the selected image's effective UID/GID before changing access:

```sh
# Check current permissions
ls -la /var/run/docker.sock

docker compose exec alloy id
```

Do not make the socket world-writable. A `:ro` socket mount does not restrict Docker API operations; daemon access is privileged. If a non-root image user cannot connect, grant only the verified socket group using an explicit `group_add` configuration, or use a restricted Docker API proxy that supports the required discovery/log endpoints.

### DNS

Add a record for `alloy.yourdomain.com` → `10.0.5.5` (Traefik).

## Quick Start

```sh
# Run on the Linux host from the repository root after completing each stack's prerequisites.
# Deploy Traefik, then Prometheus, then Loki using their README instructions.
cd alloy
cp .env.example .env
nano .env
docker compose config --quiet
docker compose up -d
```

The `traefik` and `monitoring` networks must already exist, and Loki/Prometheus must be available. There is no Promtail service in the current repository; a fresh Alloy deployment does not require stopping Loki. For an older installation, retire its old log shipper separately after verifying Alloy delivery.

Navigate to `https://alloy.yourdomain.com` for the debug UI. The **Graph** tab shows the live pipeline and whether each component is healthy.

Docker healthchecks are intentionally omitted because the upstream Alloy image does not include `wget` or `curl`. Verify availability through Prometheus scrape status, Traefik, or the Alloy debug UI instead.

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
| `PROMETHEUS_RECEIVER_PORT` | `9999` | Host port for Windows Alloy remote write |

## Monitoring the AD1 and AD2 domain controllers

Ready-to-deploy Windows configurations are in [`windows/ad1`](windows/ad1) and [`windows/ad2`](windows/ad2). Each package labels its data with the corresponding hostname and sends:

- System, Application, DNS Server, Directory Service, and DFS Replication event logs to Loki.
- A curated set of authentication and account-management Security events to Loki.
- Windows, Active Directory, DNS, DFSR, service, and per-process metrics to Prometheus.

The DNS collector uses its Perflib `metrics` subcollector only. The `wmi_stats` subcollector is disabled because the `MicrosoftDNS_Statistic` provider intermittently stalls on both Windows Server 2025 domain controllers, causing the entire Windows exporter scrape to exceed its deadline. Core DNS counters remain available as `windows_dns_*` metrics.

Both destinations use the observability host at `10.0.5.10`. Loki listens on TCP `3100`; central Alloy receives Prometheus remote-write traffic on TCP `9999` and forwards it to Prometheus over the internal monitoring network. Restrict both host ports to trusted LAN clients.

Copy the matching directory to each server and run its deployment script from an elevated PowerShell prompt:

```powershell
Set-Location C:\path\to\ad2
.\deploy.ps1
```

If Alloy is missing, the script downloads and installs the pinned signed Alloy installer directly. It then verifies both network endpoints, validates the Alloy configuration, creates the Event Log bookmark directory, installs the configuration, and restarts the Alloy service. Review the script and its installer version before running it.

Verify logs in Grafana with:

```logql
{job="windows-eventlog", host="AD2"}
```

Verify metrics with:

```promql
windows_cpu_time_total{host="AD2"}
```

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

## Operations and recovery

Restrict all published syslog/OTLP/remote-write listeners to trusted senders;
Traefik's UI middleware does not protect ingestion ports. Verify components,
recent logs and delivery of a harmless log/metric in the backend, not just the
debug UI.

Preserve host config, original images/settings and Alloy's persistent positions
state if replay continuity matters. Stop Alloy before archiving that state with
the [shared recovery procedure](../README.md#backing-up-data); restore at the
same version/ownership after Loki/Prometheus exist. Retain Windows agents'
configs/bookmarks separately. Replaying from changed positions can duplicate or
miss records; review component/config changes before updating the digest.
