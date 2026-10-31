# Loki

Log aggregation backend. Loki stores and indexes logs; Grafana queries it as a datasource. Log shipping is handled by **Grafana Alloy** (`alloy/`) which replaced Promtail — deploy Alloy separately after this stack is up.

Images in `compose.yaml` are frozen to the inventoried builds. See the [image update guide](../README.md#image-updates); `docker compose pull` alone does not upgrade them.

## Prerequisites

### 1. Create storage directory

```sh
mkdir -p /mnt/SSD/Containers/loki
chown -R 3001:3001 /mnt/SSD/Containers/loki
```

### 2. Deploy after Prometheus

Deploy Traefik first, then Prometheus to own/create `monitoring`, then Loki.
Both external networks must exist. A stopped Prometheus container does not
remove its deployed network; do not create a competing manually owned bridge.
Run Linux/Bash commands from `loki/`.

## Quick Start

```sh
cp .env.example .env
# Set LOKI_DOMAIN and review LOKI_PORT
docker compose up -d
docker compose logs -f loki
```

Verify `/ready` returns success; the configured warning log level may omit
informational startup messages.

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
Host port `${LOKI_PORT:-3100}` is also published and bypasses the Traefik LAN
allowlist. `auth_enabled: false` means direct ingest/query access must be limited
to trusted senders at the firewall.

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

Use the configured `LOKI_PORT` instead of 3100 if overridden. The Compose
healthcheck runs `loki -version` only; it is not a readiness/ingestion check.

### Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `empty ring` error on startup | Ingester hasn't joined the ring before the ratestore polls — known Loki 3.x startup timing issue | Fixed by `min_ready_duration: 0s` in the lifecycler config; recreate the container if this was just added |
| `entry too far behind` 400 errors | Entries older than `reject_old_samples_max_age` being pushed | Expected on Alloy catch-up after a redeploy — Alloy's `drop_old` stage filters these; errors stop once positions advance |
| `ingestion rate limit exceeded` 429 errors | Incoming log volume exceeds Loki's limit | Reduce noisy logs/filter or rate-limit at the collector, or review Loki capacity/limits; Docker log rotation bounds disk use, not ingestion rate |
| Grafana shows no data / datasource error | Loki not reachable on `monitoring` network | Confirm Loki container is healthy: `docker inspect loki \| grep Status` |

## Recovery

Logs are retention-limited, not a substitute for application backups. If history
must be retained, stop Loki writers and preserve the entire data path plus
inline configuration/image/settings using the
[shared recovery procedure](../README.md#backing-up-data). Restore compatible
chunks/index/config together and verify `/ready` and a known query. Coordinate
Alloy's buffering/downtime separately; do not promise lossless collection while
the backend is unavailable.
