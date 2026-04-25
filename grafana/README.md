# Grafana

Dashboard and visualization layer for the homelab. Connects to Prometheus (and optionally Loki) over the shared `monitoring` Docker network. The Prometheus datasource is provisioned automatically — no manual setup needed after first login.

## Prerequisites

**Deploy the [prometheus](../prometheus/) stack first** — it creates the `monitoring` Docker network this stack requires.

Create the persistent storage directory and set ownership:

```bash
mkdir -p /mnt/SSD/Containers/grafana
chown -R 3001:3001 /mnt/SSD/Containers/grafana
```

## Quick Start

```bash
cp .env.example .env
nano .env  # set GRAFANA_ADMIN_PASSWORD
docker compose up -d
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `GRAFANA_ADMIN_USER` | No | `admin` | Admin username |
| `GRAFANA_ADMIN_PASSWORD` | Yes | — | Admin password — Grafana will not start without it |
| `GRAFANA_PORT` | No | `3000` | Host port for the Grafana UI |

Grafana UI: `http://<host-ip>:3000`

## Datasources

The Prometheus datasource is provisioned via [provisioning/datasources/prometheus.yml](provisioning/datasources/prometheus.yml) — it points to `http://prometheus:9090` and is set as the default. No manual configuration required.

To add Loki, add a second entry to the datasources file:

```yaml
  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    editable: false
```

## Dashboards

Import dashboards by ID from [grafana.com/grafana/dashboards](https://grafana.com/grafana/dashboards). Useful starting points:

| Dashboard | ID | Purpose |
|---|---|---|
| Node Exporter Full | 1860 | Host system metrics |
| UniFi Poller | 11315 | UniFi network stats |
| Traefik | 17346 | Traefik request metrics |
| Proxmox | 10347 | Proxmox cluster metrics |

## Plugins

The following plugins are pre-installed at startup:

| Plugin | Purpose |
|---|---|
| `grafana-clock-panel` | Clock/time display panels |
| `natel-discrete-panel` | Discrete state timeline panels |
| `grafana-piechart-panel` | Pie chart panels |

## Storage

| Data | Path |
|---|---|
| Dashboards, users, settings | `/mnt/SSD/Containers/grafana` |

## Maintenance

```bash
# Update image
docker compose pull && docker compose up -d

# Backup
docker compose down
tar -czf grafana-backup-$(date +%Y%m%d).tar.gz /mnt/SSD/Containers/grafana
docker compose up -d
```
