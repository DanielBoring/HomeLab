# Monitoring Stack

Prometheus + Grafana for metrics collection and visualization, plus Loki + Promtail for log aggregation. This stack creates the shared `monitoring` Docker network that other services (such as Unpoller) attach to.

## Services

| Service | Port | Description |
|---|---|---|
| Prometheus | 9090 | Metrics collection and storage |
| Grafana | 3000 | Dashboards and visualization |
| Loki | 3100 | Log aggregation and storage |
| Promtail | internal | Log shipper — collects Docker container logs and forwards to Loki |

## Prerequisites

Create the persistent storage directories on the host before deploying:

```bash
mkdir -p /mnt/SSD/Containers/prometheus
mkdir -p /mnt/SSD/Containers/grafana
mkdir -p /mnt/SSD/Containers/loki
chown -R 3001:3001 /mnt/SSD/Containers/prometheus
chown -R 3001:3001 /mnt/SSD/Containers/grafana
chown -R 3001:3001 /mnt/SSD/Containers/loki
```

## Quick Start

### 1. Copy the environment template

```bash
cp .env.example .env
```

### 2. Edit the .env file

```bash
nano .env
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `GRAFANA_ADMIN_USER` | No | `admin` | Grafana admin username |
| `GRAFANA_ADMIN_PASSWORD` | Yes | — | Grafana admin password |
| `GRAFANA_PORT` | No | `3000` | Host port for Grafana |
| `PROMETHEUS_PORT` | No | `9090` | Host port for Prometheus |
| `LOKI_PORT` | No | `3100` | Host port for Loki |

### 3. Deploy

```bash
docker compose up -d
```

### 4. Verify

```bash
docker compose ps
docker compose logs -f prometheus
docker compose logs -f grafana
docker compose logs -f loki
docker compose logs -f promtail
```

- Prometheus UI: `http://<host-ip>:9090`
- Grafana UI: `http://<host-ip>:3000`
- Loki (API only, no UI): `http://<host-ip>:3100`

## OTLP Receiver

The Prometheus OTLP receiver is enabled via `--web.enable-otlp-receiver`, exposing an ingest endpoint at `http://prometheus:9090/api/v1/otlp/v1/metrics`.

### Trade-offs

- **Performance** — OTLP is push-based, so Prometheus now accepts inbound connections in addition to scraping. High-volume senders can overwhelm it, and translating from the OTel data model adds CPU overhead.
- **Data model mismatch** — OTel types (exponential histograms, sum/gauge distinctions) don't map cleanly to Prometheus internals; data may be silently transformed. OTel attribute names with dots are mangled into underscores.
- **Cardinality risk** — Senders control which attributes become labels. Unlike scrape targets (where you control relabeling), a poorly instrumented app can introduce unbounded cardinality.
- **Feature gaps** — The receiver is newer than the scrape path; some OTel features (e.g., exemplar handling) may lag behind.
- **Architecture** — If an OTel Collector is already in the stack, prefer routing OTLP through it and exporting to Prometheus via `prometheusremotewrite` — this gives more control over transformation and batching.

## Adding Scraped Services

To add a new service for Prometheus to scrape, add a job to [prometheus.yml](prometheus.yml):

```yaml
scrape_configs:
  - job_name: my-service
    static_configs:
      - targets: ["my-container:port"]
```

Then reload Prometheus without restarting the container:

```bash
curl -X POST http://localhost:9090/-/reload
```

The target container must be on the `monitoring` Docker network.

## Grafana Dashboards

After first login, add Prometheus as a data source:

1. Go to Connections → Data Sources → Add new
2. Select **Prometheus**
3. URL: `http://prometheus:9090`
4. Save & Test

Then import dashboards by ID from [grafana.com/grafana/dashboards](https://grafana.com/grafana/dashboards).

The following plugins are pre-installed at startup:

| Plugin | Purpose |
|---|---|
| `grafana-clock-panel` | Clock/time display panels |
| `natel-discrete-panel` | Discrete state timeline panels |
| `grafana-piechart-panel` | Pie chart panels |

## Loki

Loki is configured in [loki-config.yaml](loki-config.yaml). Logs are stored on the local filesystem and retained for **30 days**, matching Prometheus.

Promtail uses Docker service discovery (via the Docker socket) to automatically collect logs from every container on the host. Each log stream is labeled with `container`, `stream` (stdout/stderr), `compose_project`, and `compose_service`.

### Querying logs in Grafana

The Loki datasource is provisioned automatically — no manual setup needed. To explore logs:

1. Go to **Explore** in Grafana.
2. Select the **Loki** datasource.
3. Use LogQL to query, e.g.:
   ```logql
   {container="dozzle"}
   {compose_project="monitoring-stack"} |= "error"
   ```

### Useful LogQL examples

```logql
# All logs from a container
{container="traefik"}

# Error lines across all containers
{compose_project=~".+"} |= "error"

# Logs from a specific compose project
{compose_project="arrrr-stack"}

# Rate of error lines per container (for a dashboard panel)
sum by (container) (rate({compose_project=~".+"} |= "error" [5m]))
```

## Storage

| Data | Path |
|---|---|
| Prometheus metrics | `/mnt/SSD/Containers/prometheus` |
| Grafana data (dashboards, users) | `/mnt/SSD/Containers/grafana` |
| Loki log chunks and index | `/mnt/SSD/Containers/loki` |

Metrics and logs are both retained for **30 days** by default.

## Maintenance

### Update images

```bash
docker compose pull
docker compose up -d
```

### Backup

```bash
docker compose down
tar -czf monitoring-backup-$(date +%Y%m%d).tar.gz \
  /mnt/SSD/Containers/prometheus \
  /mnt/SSD/Containers/grafana \
  /mnt/SSD/Containers/loki
docker compose up -d
```
