# Calibre

Calibre desktop GUI and Calibre-Web served as Docker containers. Calibre runs a full KasmVNC desktop for library management; Calibre-Web provides a browser-based reading interface backed by the same library.

## Services

| Service | Port | Description |
|---|---|---|
| Calibre | 8085 | Desktop GUI (HTTP, via KasmVNC) |
| Calibre | 8086 | Desktop GUI (HTTPS, via KasmVNC) |
| Calibre | 8081 | Webserver GUI / content server (enable in Calibre settings) |
| Calibre-Web | 8083 | Web reading interface |

## Prerequisites

Deploy Traefik first; run Linux/Bash commands from `calibre/`. Ownership commands
below are for fresh directories only. Preserve existing media ACLs/owners.

Create persistent storage directories before deploying:

```bash
mkdir -p /mnt/SSD/Containers/calibre
mkdir -p /mnt/SSD/Containers/calibre-web
chown -R 3001:3001 /mnt/SSD/Containers/calibre
chown -R 3001:3001 /mnt/SSD/Containers/calibre-web
```

Ensure your book library is accessible at `/mnt/Data/Media/Books`. It is mounted read-write into both containers at `/books`.

## Quick Start

```bash
cp .env.example .env
# Edit .env — set CALIBRE_DOMAIN and CALIBRE_WEB_DOMAIN
docker compose up -d
```

### Verify

```bash
docker compose ps
docker compose logs -f
```

Navigate to `https://<CALIBRE_DOMAIN>` for the Calibre desktop GUI or `https://<CALIBRE_WEB_DOMAIN>` for Calibre-Web. Direct host access is also available on `http://<host-ip>:8085` and `http://<host-ip>:8083`.

## Initial Setup

### Calibre (first run)

1. Open `http://<host-ip>:8085` in your browser.
2. When prompted for a library location, set it to `/books`.
3. Optionally enable the content server: **Preferences → Sharing → Content server → Start**.

For an existing installation, use **Calibre Library → Switch/create library**, select **Use the previously existing library at the new location**, and set the location to `/books`.

### Calibre-Web (first run)

1. Open `http://<host-ip>:8083` in your browser.
2. Log in with default credentials: `admin` / `admin123` — **change immediately**.
3. Set the Calibre library location to `/books` (or the subdirectory matching your library).
4. Optional paths to configure in admin settings:
   - **Unrar**: `/usr/bin/unrar`
   - **Kepubify**: `/usr/bin/kepubify`
   - **Ebook converter**: `/usr/bin/ebook-convert`

## Configuration

| Variable | Service | Description |
|---|---|---|
| `CALIBRE_DOMAIN` | calibre | Hostname Traefik routes to the Calibre desktop GUI |
| `CALIBRE_WEB_DOMAIN` | calibre-web | Hostname Traefik routes to Calibre-Web |
| `CUSTOM_PORT` | calibre | Fixed container setting `8085`; not a dotenv control |
| `CUSTOM_HTTPS_PORT` | calibre | Fixed container setting `8086`; not a dotenv control |
| `DOCKER_MODS` | calibre-web | Fixed conversion mod (x86-64 only) |
| `PASSWORD` | calibre | Upstream optional setting; requires an explicit service environment entry |
| `CLI_ARGS` | calibre | Upstream optional setting; requires an explicit service environment entry |

> Investigate GUI logs first. Relaxing seccomp is a deliberate security change,
> not a default fix; preserve `no-new-privileges` if adding a reviewed exception.
> All four published host ports bypass Traefik middleware. Restrict them to
> trusted clients, especially the desktop if no application password is set.

## Storage

| Data | Path |
|---|---|
| Calibre config | `/mnt/SSD/Containers/calibre` |
| Calibre-Web config and database | `/mnt/SSD/Containers/calibre-web` |
| Book library (shared by Calibre and Calibre-Web, read-write) | `/mnt/Data/Media/Books` |

## Maintenance

### Update images

```bash
docker compose pull
docker compose up -d
```

### Backup

Stop both containers and any other book-library writers before backing up
**both config paths and `/mnt/Data/Media/Books`** (including `metadata.db`) as a
consistent set. Follow the [shared recovery procedure](../README.md#backing-up-data).
Restore original versions/settings/ownership, then verify Calibre's library and
Calibre-Web login/book downloads before reopening. Never restore only book files
over a different live metadata database.
