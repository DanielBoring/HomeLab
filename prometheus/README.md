# Prometheus

Metrics collection and storage for the homelab. Prometheus scrapes targets on the `monitoring` Docker network and retains data for 30 days. This stack **owns and creates** the shared `monitoring` network that Grafana, Unpoller, and pve-exporter attach to.

## Architecture

```
[traefik :8082]   [unpoller :9130]   [pve-exporter :9221]
        \                |                  /
         └──────── prometheus:9090 ─────────
                         │
                   monitoring network
                         │
                [grafana, unpoller, ...]
```

Prometheus scrapes all targets via the `monitoring` bridge network. The OTLP receiver is also enabled, accepting push-based metrics at `/api/v1/otlp/v1/metrics`.

## Prerequisites

Create the persistent storage directory and set ownership:

```bash
mkdir -p /mnt/SSD/Containers/prometheus
chown -R 3001:3001 /mnt/SSD/Containers/prometheus
```

**Deploy this stack before Grafana** — it creates the `monitoring` Docker network.

## Quick Start

```bash
cp .env.example .env
docker compose up -d
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `PROMETHEUS_PORT` | No | `9090` | Host port for the Prometheus UI and API |

## Adding Scrape Targets

Add a job to [prometheus.yml](prometheus.yml):

```yaml
scrape_configs:
  - job_name: my-service
    static_configs:
      - targets: ["my-container:port"]
```

The target container must be on the `monitoring` Docker network. Reload without restarting:

```bash
curl -X POST http://localhost:9090/-/reload
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

# Backup
docker compose down
tar -czf prometheus-backup-$(date +%Y%m%d).tar.gz /mnt/SSD/Containers/prometheus
docker compose up -d
```
