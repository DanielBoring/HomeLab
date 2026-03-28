# Monitoring Stack

Prometheus + Grafana for metrics collection and visualization. This stack creates the shared `monitoring` Docker network that other services (such as Unpoller) attach to.

## Services

| Service | Port | Description |
|---|---|---|
| Prometheus | 9090 | Metrics collection and storage |
| Grafana | 3000 | Dashboards and visualization |

## Prerequisites

Create the persistent storage directories on the host before deploying:

```bash
mkdir -p /mnt/SSD/Containers/prometheus
mkdir -p /mnt/SSD/Containers/grafana
chown -R 3001:3001 /mnt/SSD/Containers/prometheus
chown -R 3001:3001 /mnt/SSD/Containers/grafana
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

### 3. Deploy

```bash
docker compose up -d
```

### 4. Verify

```bash
docker compose ps
docker compose logs -f prometheus
docker compose logs -f grafana
```

- Prometheus UI: `http://<host-ip>:9090`
- Grafana UI: `http://<host-ip>:3000`

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

## Storage

| Data | Path |
|---|---|
| Prometheus metrics | `/mnt/SSD/Containers/prometheus` |
| Grafana data (dashboards, users) | `/mnt/SSD/Containers/grafana` |

Metrics are retained for **30 days** by default (`--storage.tsdb.retention.time=30d`).

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
  /mnt/SSD/Containers/grafana
docker compose up -d
```
