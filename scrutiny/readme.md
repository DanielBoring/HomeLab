# Scrutiny

Hard drive health dashboard powered by SMART data. Scrutiny runs `smartctl` against your drives on a schedule, stores historical metrics in a bundled InfluxDB instance, and surfaces failures — both raw SMART attribute failures and Backblaze-derived failure statistics — in a clean web UI.

This deployment uses the **omnibus** image, which bundles the web/API server, the drive collector (cron-scheduled), and InfluxDB into a single container. No separate database container is needed.

## Architecture

```
┌──────────────────────────────────────────┐
│  scrutiny (omnibus container)            │
│                                          │
│  ┌────────────┐  ┌──────────────────┐   │
│  │ collector  │  │ web / API :8080  │   │
│  │ (cron)     │  │                  │◄──┼── Traefik → browser
│  └─────┬──────┘  └────────┬─────────┘   │
│        │                  │             │
│        └──────┬───────────┘             │
│               ▼                         │
│        ┌────────────┐                   │
│        │  InfluxDB  │                   │
│        └────────────┘                   │
└──────────────────────────────────────────┘
         │
  /dev/sda, /dev/sdb, ...  (host drives passed in)
```

The collector runs on a schedule (default: 6 hours) and sends SMART data to the internal InfluxDB. The web UI reads from InfluxDB and serves the dashboard.

## Prerequisites

### 1. Create storage directories on the host

```bash
mkdir -p /mnt/SSD/Containers/scrutiny/config
mkdir -p /mnt/SSD/Containers/scrutiny/influxdb
```

### 2. Identify your drives

On the TrueNAS host, list all physical disks:

```bash
lsblk -d -o NAME,TYPE,SIZE,MODEL | grep disk
```

Or with smartctl:

```bash
smartctl --scan
```

Note the device paths (e.g. `/dev/sda`, `/dev/nvme0n1`) — you'll need to list them in `compose.yaml`.

### 3. Update the devices list in compose.yaml

Edit the `devices:` block to match your actual drives:

```yaml
devices:
  - /dev/sda
  - /dev/sdb
  - /dev/sdc
  - /dev/nvme0n1
  # add every drive you want monitored
```

Scrutiny will only see drives explicitly listed here. Drives not listed are silently ignored.

## Quick Start

```bash
cp example.env .env
# Edit .env — set SCRUTINY_DOMAIN at minimum
docker compose up -d
```

### Verify

```bash
docker compose ps
docker compose logs -f
```

Wait 30–60 seconds for InfluxDB to initialize, then navigate to `https://<SCRUTINY_DOMAIN>`. The first SMART scan runs immediately on container start; subsequent scans follow the 6-hour schedule.

## Configuration

### `.env` variables

| Variable | Default | Description |
|---|---|---|
| `TZ` | `America/New_York` | Timezone (controls cron schedule display) |
| `SCRUTINY_DOMAIN` | — | Hostname Traefik routes to Scrutiny |
| `SCRUTINY_PORT` | `8096` | Host port (direct LAN access only — Traefik ignores this) |

### `scrutiny.yaml` (optional advanced config)

For advanced configuration (collector schedule, notification webhooks, alert thresholds), drop a `scrutiny.yaml` in `/mnt/SSD/Containers/scrutiny/config/`. Scrutiny reads it on startup.

Example — change the collector schedule to every 12 hours:

```yaml
# /mnt/SSD/Containers/scrutiny/config/scrutiny.yaml
collector:
  cron: "0 */12 * * *"
```

Full config reference: https://github.com/AnalogJ/scrutiny/blob/master/example.scrutiny.yaml

## Capabilities

Scrutiny requires two Linux capabilities to read SMART data:

| Capability | Required for |
|---|---|
| `SYS_RAWIO` | SATA/SAS ATA passthrough (most spinning and SATA SSD drives) |
| `SYS_ADMIN` | NVMe IOCTL passthrough (NVMe SSDs) |

These are granted via `cap_add` in `compose.yaml` — not full `privileged: true`. If you have no NVMe drives, `SYS_ADMIN` can be removed from the compose file.

## Storage

| Data | Host path |
|---|---|
| Scrutiny config | `/mnt/SSD/Containers/scrutiny/config` |
| InfluxDB time-series data | `/mnt/SSD/Containers/scrutiny/influxdb` |

## Notifications

Scrutiny can push notifications to Slack, Discord, PagerDuty, email, and others via [shoutrrr](https://containrrr.dev/shoutrrr/). Configure via `scrutiny.yaml`:

```yaml
notify:
  urls:
    - "discord://token@webhookid"
    - "slack://tokenA/tokenB/tokenC"
```

Notifications fire when a drive's SMART status changes (passes → failed or failed → passes).

## Maintenance

### Force an immediate SMART scan

```bash
docker exec scrutiny scrutiny-collector-metrics run
```

### Update image

```bash
docker compose pull
docker compose up -d
```

### Check InfluxDB health

```bash
docker exec scrutiny influx ping
```
