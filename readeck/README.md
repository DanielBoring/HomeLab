# Readeck

Self-hosted read-later app. Save articles, pages, and links from any device; Readeck strips away the noise and stores a clean readable copy so the content survives link rot. Supports tagging, highlights, annotations, full-text search, and an RSS feed of your saved items.

Run it when you want a Pocket/Instapaper replacement that keeps your reading list on your own infrastructure.

## Architecture

```
Browser / mobile / browser extension
            │
            ▼
      Traefik (TLS)
            │
            ▼
    readeck:8000 (Next.js)
            │
            ▼
    /readeck (SQLite + article data)
```

Single container — Readeck bundles SQLite so no separate database service is needed.

## Prerequisites

### Create storage directory

```bash
mkdir -p /mnt/SSD/Containers/readeck/data
```

## Quick Start

```bash
cp .env.example .env
# Edit .env — set READECK_DOMAIN
docker compose up -d
docker compose logs -f app
```

Navigate to `https://<READECK_DOMAIN>` and create your account — the first registered user becomes admin.

## Configuration

| Variable | Required | Description |
|---|---|---|
| `READECK_DOMAIN` | Yes | Hostname Traefik routes to Readeck |

All other settings are fixed in `compose.yaml`:

| Variable | Value | Description |
|---|---|---|
| `READECK_LOG_LEVEL` | `info` | Log verbosity (`error`, `warn`, `info`, `debug`) |
| `READECK_SERVER_HOST` | `0.0.0.0` | Listen on all interfaces |
| `READECK_SERVER_PORT` | `8000` | Internal container port |
| `READECK_ALLOWED_HOSTS` | `${READECK_DOMAIN},localhost` | Hostnames accepted by the server — required for reverse proxy |
| `READECK_USE_X_FORWARDED` | `true` | Trust `X-Forwarded-For` headers from Traefik |

### PostgreSQL (optional)

Readeck supports PostgreSQL if you outgrow SQLite. Add a `db` service and set:

```yaml
environment:
  - READECK_DATABASE_SOURCE=postgresql://readeck:password@db:5432/readeck
```

Use `openssl rand -hex 32` for the password (base64 breaks URL parsing).

## Storage

| Data | Host Path |
|---|---|
| SQLite database, article archives, thumbnails | `/mnt/SSD/Containers/readeck/data` |

## Maintenance

### Update

```bash
docker compose pull
docker compose up -d
```

### Backup

```bash
docker compose down
tar -czf readeck-backup-$(date +%Y%m%d).tar.gz /mnt/SSD/Containers/readeck
docker compose up -d
```

### Restore

```bash
docker compose down
rm -rf /mnt/SSD/Containers/readeck/data
tar -xzf readeck-backup-<date>.tar.gz -C /
docker compose up -d
```
