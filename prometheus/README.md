# Prometheus

Metrics collection and storage for the homelab with 30-day retention. Prometheus joins `traefik` for its web route and the Traefik scrape target. This stack **owns and creates** the shared `monitoring` network used by Grafana, Loki, Alloy, Unpoller, and exporters.

Images in `compose.yaml` are frozen to the inventoried builds. See the [image update guide](../README.md#image-updates); `docker compose pull` alone does not upgrade them.

## Architecture

```text
[traefik :8082] -------- traefik bridge ------+
                                            |
                                     prometheus:9090
                                            |
                                      monitoring bridge
                                        /         \
                         [unpoller :9130]     [proxmox-exporter :9221]
                         [grafana, loki, alloy, ...]
```

Prometheus scrapes monitoring services through the `monitoring` bridge and Traefik through the shared `traefik` bridge. The OTLP receiver is also enabled, accepting push-based metrics at `/api/v1/otlp/v1/metrics`.

## Prerequisites

Deploy [Traefik](../traefik/README.md) first to create `traefik`. Run the commands below from this repository's `prometheus` directory on the Linux host.

Create the persistent storage directory, copy the config, and set ownership:

```bash
mkdir -p /mnt/SSD/Containers/prometheus
cp prometheus.yml /mnt/SSD/Containers/prometheus/prometheus.yml
chown -R 3001:3001 /mnt/SSD/Containers/prometheus
```

**Deploy this stack before Grafana, Loki, Unpoller, and proxmox-exporter** — it creates the `monitoring` Docker network.

## Quick Start

```bash
cp .env.example .env
nano .env  # set PROMETHEUS_DOMAIN
docker compose up -d
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `PROMETHEUS_DOMAIN` | Yes | — | Hostname Traefik routes to Prometheus |

Prometheus UI: `https://<PROMETHEUS_DOMAIN>` (via Traefik, LAN only)

## Adding Scrape Targets

Edit `/mnt/SSD/Containers/prometheus/prometheus.yml` on the host:

```yaml
scrape_configs:
  - job_name: my-service
    static_configs:
      - targets: ["my-container:port"]
```

The target container must share a Docker network with Prometheus. Use `monitoring` for monitoring services; Traefik's existing `traefik:8082` target uses the shared `traefik` bridge. Neither scrape path requires a published host port. Reload from a shell that can reach the Prometheus container:

```bash
docker exec prometheus wget --quiet --method=POST -O- http://localhost:9090/-/reload
```

## OTLP Receiver

Enabled via `--web.enable-otlp-receiver`. Ingest endpoint: `http://prometheus:9090/api/v1/otlp/v1/metrics`.

Trade-offs to be aware of:
- Push-based ingest adds CPU overhead for OTel→Prometheus translation
- OTel attribute names with dots are mangled to underscores
- Senders control label cardinality — a poorly instrumented app can cause unbounded cardinality
- If an OTel Collector is in the stack, prefer routing through it with `prometheusremotewrite` for better control

## Storage

| Data | Path |
|---|---|
| Metrics (30-day retention) | `/mnt/SSD/Containers/prometheus` |

## Maintenance

```bash
# Update image
docker compose pull && docker compose up -d

```

Ownership/copy steps are for fresh setup; compare existing host config before
replacing it. Validate edited scrape config with
`docker compose exec prometheus promtool check config /etc/prometheus/prometheus.yml`
before a planned reload. Preserve config/settings and, if history matters,
the complete stopped TSDB using the [shared recovery procedure](../README.md#backing-up-data).
Use `stop`, not network removal, for owner-stack maintenance; coordinate
consumers separately. Restore at the compatible version and verify targets and
a historical query. Review retention/migrations before changing tag **and**
digest.
