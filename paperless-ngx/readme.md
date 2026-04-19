# Paperless-ngx

Self-hosted document management system. OCRs, indexes, and archives documents — making them full-text searchable with automatic classification by correspondent, document type, and tags.

## Services

| Service | Port | Description |
|---|---|---|
| webserver | 8000 | Web UI and REST API (proxied via Traefik) |
| db | internal | PostgreSQL 17 — document metadata and state |
| broker | internal | Redis 7 — task queue for Celery workers |
| tika | internal | Apache Tika — text extraction from Office documents |
| gotenberg | internal | Gotenberg — Office-to-PDF conversion via Chromium |

`db`, `broker`, `tika`, and `gotenberg` are on an isolated `paperless` bridge network. Only `webserver` is connected to the `traefik` network.

## Prerequisites

### 1. Create storage directories

```bash
mkdir -p /mnt/SSD/Containers/paperless/{data,media,consume,export,redis}
mkdir -p /mnt/SSD/Containers/paperless/db
chown -R 3001:3001 /mnt/SSD/Containers/paperless/data
chown -R 3001:3001 /mnt/SSD/Containers/paperless/media
chown -R 3001:3001 /mnt/SSD/Containers/paperless/consume
chown -R 3001:3001 /mnt/SSD/Containers/paperless/export
chown -R 3001:3001 /mnt/SSD/Containers/paperless/redis
# db is owned by the postgres user inside the container — do not chown it
```

### 2. Generate secrets

```bash
# Secret key
openssl rand -hex 32

# Database password (use a different value)
openssl rand -base64 32
```

Paste the outputs into `.env`.

## Quick Start

```bash
cp .env.example .env
# Edit .env — fill in PAPERLESS_SECRET_KEY, PAPERLESS_DBPASS,
#              PAPERLESS_ADMIN_PASSWORD, and PAPERLESS_DOMAIN
docker compose up -d
docker compose logs -f webserver
```

First startup takes 30–60 seconds while Django runs migrations and creates the admin account. Navigate to `https://<PAPERLESS_DOMAIN>` and log in with your admin credentials.

> **Note:** `PAPERLESS_ADMIN_USER` / `PAPERLESS_ADMIN_PASSWORD` only create the account on the very first run. After that, manage users through the web UI — changing these vars has no effect.

## Configuration

`.env` variables:

| Variable | Required | Description |
|---|---|---|
| `PAPERLESS_SECRET_KEY` | Yes | Django secret key — generate with `openssl rand -hex 32` |
| `PAPERLESS_DBPASS` | Yes | PostgreSQL password |
| `PAPERLESS_ADMIN_USER` | Yes | Initial admin username (first run only) |
| `PAPERLESS_ADMIN_PASSWORD` | Yes | Initial admin password (first run only) |
| `PAPERLESS_ADMIN_MAIL` | Yes | Initial admin email (first run only) |
| `TZ` | No | Timezone (default: `America/New_York`) |
| `PAPERLESS_OCR_LANGUAGE` | No | Tesseract language (default: `eng`). Use `+` for multiple: `eng+fra` |
| `PAPERLESS_DOMAIN` | Yes | Hostname Traefik routes to Paperless |
| `PAPERLESS_PORT` | No | Host port for direct access (default: `8010`) |

Commented-out options in `compose.yaml`:

| Variable | Description |
|---|---|
| `PAPERLESS_CONSUMER_POLLING` | Set to `10` if inotify doesn't work on TrueNAS |
| `PAPERLESS_FILENAME_FORMAT` | Template for how files are named on disk |
| `PAPERLESS_TASK_WORKERS` | Number of parallel OCR workers (increase on multi-core) |
| `PAPERLESS_WEBSERVER_WORKERS` | Gunicorn processes (increase for concurrent users) |

## Storage

| Data | Host Path |
|---|---|
| Search index, classifier, logs | `/mnt/SSD/Containers/paperless/data` |
| Originals, archive PDFs, thumbnails | `/mnt/SSD/Containers/paperless/media` |
| Consumption inbox | `/mnt/SSD/Containers/paperless/consume` |
| Export / backup output | `/mnt/SSD/Containers/paperless/export` |
| PostgreSQL data | `/mnt/SSD/Containers/paperless/db` |
| Redis data | `/mnt/SSD/Containers/paperless/redis` |

## Consuming Documents

Drop files into `/mnt/SSD/Containers/paperless/consume` — they are picked up automatically and processed (OCR, classification, archive PDF generation).

Subdirectories are supported (`PAPERLESS_CONSUMER_RECURSIVE=true`) and folder names become tags (`PAPERLESS_CONSUMER_SUBDIRS_AS_TAGS=true`).

Other methods: web UI upload, REST API, email (configure in Admin → Mail).

## Maintenance

### Update images

```bash
docker compose pull
docker compose up -d
docker compose logs -f webserver   # watch for migration output
```

### Export (backup)

```bash
docker compose exec -T webserver document_exporter /usr/src/paperless/export
tar -czf paperless-export-$(date +%Y%m%d).tar.gz /mnt/SSD/Containers/paperless/export
```

The exporter is incremental — re-running only exports changed documents.

### Restore from export

```bash
# Deploy a fresh instance at the same version, then:
docker compose exec webserver document_importer /usr/src/paperless/export
```

### Rebuild search index

```bash
docker compose exec webserver document_index reindex
```

### Sanity check

```bash
docker compose exec webserver document_sanity_checker
```

Detects missing originals, checksum mismatches, missing thumbnails, and permission errors.

### Full backup (volumes)

```bash
docker compose down
tar -czf paperless-volumes-$(date +%Y%m%d).tar.gz \
  /mnt/SSD/Containers/paperless
docker compose up -d
```
