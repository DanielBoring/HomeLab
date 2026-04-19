# Loki + Promtail

Log aggregation stack. Loki stores and indexes logs; Promtail ships them from Docker containers and the TrueNAS systemd journal. Grafana queries Loki as a datasource via the shared `loki` Docker network.

## Services

| Service | Port | Description |
|---|---|---|
| loki | 3100 | Log storage and query API |
| promtail | internal | Log shipper — Docker socket + systemd journal |

## Prerequisites

### 1. Create storage directories

```bash
mkdir -p /mnt/SSD/Containers/loki
mkdir -p /mnt/SSD/Containers/promtail
chown -R 3001:3001 /mnt/SSD/Containers/loki
# promtail runs as root (required for Docker socket) — do not chown
```

### 2. Deploy before monitoring-stack

Loki creates the `loki` Docker network. Grafana (in `monitoring-stack`) joins it as an external network, so **this stack must be up before monitoring-stack is deployed**.

## Quick Start

```bash
docker compose up -d
docker compose logs -f loki
```

Loki is ready when logs show `level=info msg="Loki ready"`. Promtail waits for the Loki healthcheck before starting.

## Configuration

`.env` variables:

| Variable | Required | Description |
|---|---|---|
| `LOKI_PORT` | No | Host port for direct access (default: `3100`) |

Most configuration lives in `loki-config.yaml` and `promtail-config.yaml` — not in `.env`.

## Loki Config (`loki-config.yaml`)

| Setting | Value | Notes |
|---|---|---|
| `retention_period` | `30d` | Logs older than 30 days are deleted by the compactor |
| `reject_old_samples_max_age` | `168h` | Entries older than 7 days are rejected at ingestion |
| `ingestion_rate_mb` | `16` | Per-tenant ingestion rate cap (raised from 4MB default) |
| `ingestion_burst_size_mb` | `32` | Burst allowance above the rate cap |
| `schema` | `v13 / tsdb` | Current recommended schema |

## Promtail Config (`promtail-config.yaml`)

Two scrape jobs:

| Job | Source | Labels |
|---|---|---|
| `truenas-journal` | systemd journal (last 12h on startup) | `job`, `host`, `unit`, `level` |
| `docker` | Docker socket — all containers | `container`, `stream`, `compose_project`, `compose_service` |

### Drop stage

The Docker job drops entries older than 7 days before sending to Loki. This prevents 400 errors and rate limit spikes when Promtail restarts and re-reads container log files from the beginning.

### Positions file

Promtail saves its read position for each container log to `/var/promtail/positions.yaml` (persisted to `/mnt/SSD/Containers/promtail`). This means restarts resume from where they left off rather than re-reading all logs from scratch.

> **Note:** When a container is recreated (e.g. after a stack redeploy), Docker assigns it a new container ID and a new log file. Promtail will start reading the new log file from the beginning. The drop stage ensures only recent entries are sent to Loki.

## Storage

| Data | Host Path |
|---|---|
| Loki chunks, index, rules | `/mnt/SSD/Containers/loki` |
| Promtail read positions | `/mnt/SSD/Containers/promtail` |

## Networking

Loki creates the `loki` bridge network. Services that need to query Loki (e.g. Grafana) should join it as an external network:

```yaml
networks:
  loki:
    external: true
```

Grafana's provisioned Loki datasource points to `http://loki:3100` — this resolves correctly as long as Grafana is on the `loki` network.

## Maintenance

### View logs

```bash
docker compose logs -f loki
docker compose logs -f promtail
```

### Update images

```bash
docker compose pull
docker compose up -d
```

### Check Loki health

```bash
curl http://localhost:3100/ready
curl http://localhost:3100/metrics | grep loki_ingester
```

### Check Promtail targets

```bash
curl http://localhost:9080/targets
```

Lists all discovered Docker containers and their current scrape status.

### Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `empty ring` 500 errors | Loki ingester crashed (usually OOM under log flood) | Truncate the offending container's log file: `truncate -s 0 $(docker inspect <name> --format='{{.LogPath}}')`, then restart promtail |
| `entry too far behind` 400 errors | Entries older than `reject_old_samples_max_age` | Expected on catch-up — drop stage filters these; errors stop once positions advance |
| `ingestion rate limit exceeded` 429 errors | Too many logs being sent at once | Transient on startup catch-up; persistent if a container generates excessive logs — add `logging.options.max-size` to that container's compose |
| Promtail can't connect to Loki | Loki not ready or network issue | Promtail depends on Loki healthcheck — wait for Loki to report ready |
