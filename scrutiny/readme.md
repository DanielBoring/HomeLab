# Scrutiny

Hard drive health dashboard powered by SMART data. Scrutiny runs `smartctl` against your drives on a schedule, stores historical metrics in a bundled InfluxDB instance, and surfaces failures — both raw SMART attribute failures and Backblaze-derived failure statistics — in a clean web UI.

This deployment uses the **omnibus** image, which bundles the web/API server, the drive collector (cron-scheduled), and InfluxDB into a single container. No separate database container is needed.

## Architecture

```text
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

The collector runs on the omnibus image's cron schedule. Current upstream
defaults to **daily at midnight**, not every six hours; confirm your selected
image because this stack still uses an un-inventoried moving tag. The web UI
reads historical data from InfluxDB.

## Prerequisites

Deploy Traefik first. Run Bash commands from `scrutiny/` on the Linux host.

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
cp .env.example .env
# Edit .env — set SCRUTINY_DOMAIN at minimum
docker compose up -d
```

### Verify

```bash
docker compose ps
docker compose logs -f
```

Allow InfluxDB to initialize, then open `https://<SCRUTINY_DOMAIN>`. Check logs
and the last collection timestamp; container readiness does not prove a scan
ran or that every drive was included.

## Configuration

### `.env` variables

| Variable | Default | Description |
|---|---|---|
| `TZ` | `America/New_York` | Timezone (controls cron schedule display) |
| `SCRUTINY_DOMAIN` | — | Hostname Traefik routes to Scrutiny |
| `SCRUTINY_PORT` | `8096` | Published host port; bypasses Traefik, so restrict it separately |

### `scrutiny.yaml` (optional advanced config)

For notification webhooks and alert settings, use the version-matching
`scrutiny.yaml`. The omnibus **cron schedule** is instead set through
`COLLECTOR_CRON_SCHEDULE` in the container environment. It is not passed from
`.env` by this stack. To request a twelve-hour schedule, merge this into the
existing service environment and recreate it during planned maintenance:

```yaml
environment:
  - COLLECTOR_CRON_SCHEDULE=0 */12 * * *
```

Full config reference: https://github.com/AnalogJ/scrutiny/blob/master/example.scrutiny.yaml

Schedule source checked 2026-10-13:
[omnibus cron setup](https://github.com/AnalogJ/scrutiny/blob/master/rootfs/etc/cont-init.d/50-cron-config).

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

## Backup and recovery

Preserve `config`, `influxdb`, original Compose/device mappings and private
settings with the [shared stopped-writer procedure](../README.md#backing-up-data).
Restore at the same image version, verify historical drive records and settings,
then verify current drive identities before scheduling scans. Backups of SMART
history do not protect the contents of the disks being monitored.
