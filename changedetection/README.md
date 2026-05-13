# ChangeDetection

Website change monitoring with automatic alerts. Point it at any URL and it notifies you when the page content changes — useful for tracking price drops, stock availability, policy updates, job postings, or anything on the web that doesn't have an RSS feed.

When to run this over alternatives like Visualping or built-in browser features: ChangeDetection is self-hosted, stores full history, supports complex filtering (XPath, CSS selectors, regex), and integrates with nearly every notification service via Apprise. It also handles JavaScript-heavy sites that simpler HTTP-polling tools can't reach.

## Architecture

```
Browser
  │
  └─► changedetection :5000  ──► changedetection-playwright :3000 (JS rendering)
                         │
                         └─► flaresolverr :8191 (Cloudflare bypass)
```

| Container | Image | Role |
|---|---|---|
| `changedetection` | lscr.io/linuxserver/changedetection.io | Main app and web UI |
| `changedetection-playwright` | dgtlmoon/sockpuppetbrowser | Headless Chromium for JS-rendered pages |

**Fetch methods — when to use each:**

| Method | When to use |
|---|---|
| HTTP (default) | Simple HTML pages, APIs, RSS feeds |
| Playwright/Chrome | Pages that require JavaScript to render content |
| FlareSolverr | Cloudflare-protected sites that block scraping |

### Networks

| Network | Type | Purpose |
|---|---|---|
| `changedetection` | internal bridge | Allows the main container to reach playwright by service name |
| `flaresolverr` | external | Shared with the FlareSolverr stack; allows `http://flaresolverr:8191` to resolve |

## Prerequisites

1. **FlareSolverr stack deployed first** — it creates the external `flaresolverr` network this stack depends on. If deploying without FlareSolverr, remove the `flaresolverr` network entries from `compose.yaml`.

2. **Host storage directory:**
   ```sh
   mkdir -p /mnt/SSD/Containers/changedetection
   chown -R 3001:3001 /mnt/SSD/Containers/changedetection
   ```

## Quick Start

```sh
cp example.env .env
# Edit .env as needed
docker compose up -d
```

Open `http://<host-ip>:5000`.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TZ` | `America/New_York` | Container timezone |
| `CHANGEDETECTION_PORT` | `5000` | Host port the UI is exposed on |

Variables hardcoded in `compose.yaml` (rarely need changing):

| Variable | Service | Description |
|---|---|---|
| `PUID` / `PGID` | changedetection | Run as UID/GID `3001` |
| `BASE_URL` | changedetection | Uncomment only if behind a reverse proxy with a subpath |
| `PLAYWRIGHT_DRIVER_URL` | changedetection | WebSocket URL of the browser sidecar |
| `DEFAULT_LAUNCH_ARGS` | changedetection-playwright | Chrome launch flags |

## FlareSolverr Integration

After deploying, configure the Flaresolverr URL in the UI:

**Settings → General → Requests → FlareSolverr API URL**
```
http://flaresolverr:8191
```

Per-watch, select **FlareSolverr** as the fetch method for any Cloudflare-protected site.

## Notifications

ChangeDetection uses [Apprise](https://github.com/caronc/apprise) for notifications. Configure URLs under **Settings → Notifications**. Common examples:

```
# Discord
discord://webhook_id/webhook_token

# Gotify
gotify://hostname/token

# Email (SMTP)
mailto://user:password@smtp.host/to@address
```

## Storage

| Data | Host path |
|---|---|
| Config and watch data | `/mnt/SSD/Containers/changedetection/` |

## Maintenance

```sh
# Update images
docker compose pull && docker compose up -d

# Backup (stops briefly)
docker compose down
tar -czf changedetection-backup-$(date +%Y%m%d).tar.gz /mnt/SSD/Containers/changedetection
docker compose up -d
```
