# Loki

Log aggregation backend. Loki stores and indexes logs; Grafana queries it as a datasource. Log shipping is handled by **Grafana Alloy** (`alloy/`) which replaced Promtail — deploy Alloy separately after this stack is up.

## Prerequisites

### 1. Create storage directory

```sh
mkdir -p /mnt/SSD/Containers/loki
chown -R 3001:3001 /mnt/SSD/Containers/loki
```

### 2. Deploy after Prometheus

Loki joins the `monitoring` Docker network as an external consumer. Prometheus (`prometheus/`) creates that network, so **Prometheus must be up before this stack is deployed**. Docker Compose validates external networks at startup and fails immediately if they don't exist — there is no retry. If you need to bring Loki up while Prometheus is down, pre-create the network manually:

```sh
docker network create monitoring
```

## Quick Start

```sh
docker compose up -d
docker compose logs -f loki
```

Loki is ready when logs show `level=info msg="Loki ready"`.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `LOKI_DOMAIN` | Yes | Traefik subdomain |
| `LOKI_PORT` | No | Host port for direct access (default: `3100`) |

## Loki Config

Config is defined inline in `compose.yaml` under the `loki-config` Docker config block. Changes require a full container recreate (`docker compose up -d --force-recreate`) — a plain restart does not re-read inline config.

| Setting | Value | Notes |
|---|---|---|
| `retention_period` | `30d` | Logs older than 30 days deleted by the compactor |
| `reject_old_samples_max_age` | `168h` | Entries older than 7 days rejected at ingestion |
| `ingestion_rate_mb` | `16` | Per-tenant ingestion rate cap (raised from 4 MB default) |
| `ingestion_burst_size_mb` | `32` | Burst allowance above the rate cap |
| `schema` | `v13 / tsdb` | Current recommended schema |
| `min_ready_duration` | `0s` | Ingester joins the ring immediately — prevents `empty ring` errors on startup |

## Storage

| Data | Host Path |
|---|---|
| Chunks, index, rules, compactor | `/mnt/SSD/Containers/loki` |

## Networking

Loki joins the shared `monitoring` bridge network (created by `prometheus/`). Grafana reaches Loki at `http://loki:3100`. Alloy pushes logs to the same endpoint from the `monitoring` network.

Loki also joins the `traefik` network so its query API is reachable at `${LOKI_DOMAIN}` for external Grafana instances or direct API access.

## Maintenance

### View logs

```sh
docker compose logs -f loki
```

### Update image

```sh
docker compose pull
docker compose up -d --force-recreate
```

### Check health

```sh
curl http://localhost:3100/ready
curl http://localhost:3100/metrics | grep loki_ingester
```

### Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `empty ring` error on startup | Ingester hasn't joined the ring before the ratestore polls — known Loki 3.x startup timing issue | Fixed by `min_ready_duration: 0s` in the lifecycler config; recreate the container if this was just added |
| `entry too far behind` 400 errors | Entries older than `reject_old_samples_max_age` being pushed | Expected on Alloy catch-up after a redeploy — Alloy's `drop_old` stage filters these; errors stop once positions advance |
| `ingestion rate limit exceeded` 429 errors | Log flood from a container | Transient on startup; persistent if a container generates excessive logs — add `logging.options.max-size` to that container's compose |
| Grafana shows no data / datasource error | Loki not reachable on `monitoring` network | Confirm Loki container is healthy: `docker inspect loki \| grep Status` |
