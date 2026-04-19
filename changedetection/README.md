# Changedetection.io

Website change detection and monitoring. Watches URLs for content changes and sends notifications. Backed by a Playwright/Chrome browser for full JavaScript rendering and Visual Selector support.

## Services

| Service | Port | Description |
|---|---|---|
| changedetection | 5000 | Web UI |
| playwright-chrome | internal | Headless Chromium browser (Playwright) |

`playwright-chrome` is not exposed outside the stack — changedetection communicates with it directly over the internal Compose network.

## Prerequisites

Create the persistent storage directory before deploying:

```bash
mkdir -p /mnt/SSD/Containers/changedetection
chown -R 3001:3001 /mnt/SSD/Containers/changedetection
```

## Quick Start

```bash
cp .env.example .env
# Edit .env if needed, then:
docker compose up -d
```

### Verify

```bash
docker compose ps
docker compose logs -f
```

Navigate to `http://<host-ip>:5000` to access the web UI.

## Configuration

`.env` variables:

| Variable | Default | Description |
|---|---|---|
| `TZ` | `America/New_York` | Timezone |
| `CHANGEDETECTION_PORT` | `5000` | Host port for the web UI |

Hardcoded in `compose.yaml`:

| Variable | Service | Description |
|---|---|---|
| `PUID` / `PGID` | changedetection | Run as this user/group (`3001`) |
| `BASE_URL` | changedetection | Full public URL — uncomment only if behind a reverse proxy with a subpath |
| `PLAYWRIGHT_DRIVER_URL` | changedetection | WebSocket URL of the Playwright browser (`ws://playwright-chrome:3000`) |
| `DEFAULT_LAUNCH_ARGS` | playwright-chrome | Chrome launch flags (default: `--window-size=1920,1080`) |

## Storage

| Data | Path |
|---|---|
| Changedetection config and watch data | `/mnt/SSD/Containers/changedetection` |

## Maintenance

### Update images

```bash
docker compose pull
docker compose up -d
```

### Backup

```bash
docker compose down
tar -czf changedetection-backup-$(date +%Y%m%d).tar.gz \
  /mnt/SSD/Containers/changedetection
docker compose up -d
```
