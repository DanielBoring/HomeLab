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

Create persistent storage directories before deploying:

```bash
mkdir -p /mnt/SSD/Containers/calibre
mkdir -p /mnt/SSD/Containers/calibre-web
chown -R 3001:3001 /mnt/SSD/Containers/calibre
chown -R 3001:3001 /mnt/SSD/Containers/calibre-web
```

Ensure your book library is accessible at `/mnt/Data/Media/Books` (mounted read-write into Calibre-Web at `/books`).

## Quick Start

```bash
docker compose up -d
```

No `.env` file required — all configuration is in `compose.yaml`.

### Verify

```bash
docker compose ps
docker compose logs -f
```

Navigate to `http://<host-ip>:8085` to access the Calibre desktop GUI.

## Initial Setup

### Calibre (first run)

1. Open `http://<host-ip>:8085` in your browser.
2. When prompted for a library location, set it to `/config/Calibre Library`.
3. Optionally enable the content server: **Preferences → Sharing → Content server → Start**.

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
| `CUSTOM_PORT` | calibre | Remaps the HTTP desktop GUI port (default: 8080) |
| `CUSTOM_HTTPS_PORT` | calibre | Remaps the HTTPS desktop GUI port (default: 8181) |
| `DOCKER_MODS` | calibre-web | Adds ebook conversion support (x86-64 only) |
| `PASSWORD` | calibre | Optional password for the KasmVNC desktop |
| `CLI_ARGS` | calibre | Optional extra arguments passed to the Calibre startup command |

> If the Calibre desktop GUI fails to render on your Docker host, uncomment `security_opt: seccomp:unconfined` in `compose.yaml`.

## Storage

| Data | Path |
|---|---|
| Calibre config and library | `/mnt/SSD/Containers/calibre` |
| Calibre-Web config and database | `/mnt/SSD/Containers/calibre-web` |
| Book library (shared, read-write) | `/mnt/Data/Media/Books` |

## Maintenance

### Update images

```bash
docker compose pull
docker compose up -d
```

### Backup

```bash
docker compose down
tar -czf calibre-backup-$(date +%Y%m%d).tar.gz \
  /mnt/SSD/Containers/calibre \
  /mnt/SSD/Containers/calibre-web
docker compose up -d
```

The book files at `/mnt/Data/Media/Books` should be backed up separately as part of your media backup strategy.
