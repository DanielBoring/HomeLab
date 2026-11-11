# Paperless-ngx

Self-hosted document management system. OCRs, indexes, and archives documents — making them full-text searchable with automatic classification by correspondent, document type, and tags.

Images in `compose.yaml` are frozen to the inventoried builds. See the [image update guide](../README.md#image-updates); `docker compose pull` alone does not upgrade them.

**Existing PostgreSQL 17 installations:** follow the [PostgreSQL 18 migration runbook](POSTGRESQL-18-UPGRADE.md) before deploying this Compose. Changing the image and mount without a logical restore does not upgrade the database.

## Services

| Service | Port | Description |
|---|---|---|
| webserver | 8000 | Web UI and REST API (proxied via Traefik) |
| db | internal | PostgreSQL 18 — document metadata and state |
| broker | internal | Redis 7 — task queue for Celery workers |
| tika | internal | Apache Tika — text extraction from Office documents |
| gotenberg | internal | Gotenberg — Office-to-PDF conversion via Chromium |

`db`, `broker`, `tika`, and `gotenberg` are on an isolated `paperless` bridge network. Only `webserver` is connected to the `traefik` network.

## Prerequisites

Deploy Traefik first. Run Linux/Bash commands from `paperless-ngx/`. Directory
creation/ownership below is for a fresh installation; preserve restored owners
and do not chown PostgreSQL/Redis state to the app's UID.

### 1. Create storage directories

```bash
mkdir -p /mnt/SSD/Containers/paperless/{data,media,consume,export,redis}
mkdir -p /mnt/SSD/Containers/paperless/db/18/docker
# Fresh PG18 storage only: prepare the full parent tree for image UID/GID 999.
chown 999:999 /mnt/SSD/Containers/paperless/db{,/18,/18/docker}
chmod 700 /mnt/SSD/Containers/paperless/db{,/18,/18/docker}
chown -R 3001:3001 /mnt/SSD/Containers/paperless/data
chown -R 3001:3001 /mnt/SSD/Containers/paperless/media
chown -R 3001:3001 /mnt/SSD/Containers/paperless/consume
chown -R 3001:3001 /mnt/SSD/Containers/paperless/export
# PostgreSQL and Redis manage their internal users; do not blanket-chown them.
# On TrueNAS, also run the isolated UID 999 ACL access probe in the migration runbook.
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
| PostgreSQL 18 parent mount (`18/docker` is PGDATA) | `/mnt/SSD/Containers/paperless/db` |
| Redis data | `/mnt/SSD/Containers/paperless/redis` |

## Consuming Documents

Drop files into `/mnt/SSD/Containers/paperless/consume` — they are picked up automatically and processed (OCR, classification, archive PDF generation).

Subdirectories are supported (`PAPERLESS_CONSUMER_RECURSIVE=true`) and folder names become tags (`PAPERLESS_CONSUMER_SUBDIRS_AS_TAGS=true`).

Other methods: web UI upload, REST API, email (configure in Admin → Mail).

## Maintenance

### Update images

Review application/database migrations and preserve the full recovery set
before changing literal image tag/digest references; pulling the same pins is
not an upgrade. For PostgreSQL 17 to 18, use the [migration runbook](POSTGRESQL-18-UPGRADE.md),
which preserves the original app pin and coordinates the data restore.

```bash
docker compose pull
docker compose up -d
docker compose logs -f webserver   # watch for migration output
```

### Export (backup)

Pause consumption and other application writers first. Run the entire block on
Linux from `paperless-ngx/`; set `BACKUP_ROOT` to an existing private backup
directory outside the checkout and source tree.

```bash
(
  set -euo pipefail
  umask 077
  root="$(realpath -e "${BACKUP_ROOT:?Set a private backup directory}")"
  source="$(realpath -e /mnt/SSD/Containers/paperless/export)"
  checkout="$(realpath ..)"
  case "$root/" in "$source/"*|"$checkout/"*) printf "Unsafe backup destination.\n" >&2; exit 1 ;; esac
  docker compose exec -T webserver document_exporter /usr/src/paperless/export
  archive="$(mktemp "$root/paperless-export.XXXXXX.tar.gz")"
  tar --acls --xattrs --numeric-owner -czf "$archive" -C "$source" .
  tar -tzf "$archive" > /dev/null
  sha256sum "$archive" > "$archive.sha256"
  printf "Checked export archive: %s\n" "$archive"
)
```

Verify the export completed before archiving; use fail-fast handling and a
protected destination outside the source path. Check the selected version's
export options: do not assume a successful archive means the exporter succeeded.
Keep unprocessed consume files and private deployment settings separately.

### Restore from export

```bash
# Deploy a fresh instance at the same version, then:
docker compose exec webserver document_importer /usr/src/paperless/export
```

Prepare that isolated instance with its own empty database/media paths,
required host directories and original relevant settings. Extract the verified
export into its mounted export directory, block ingress/consumption, and only
then import. Check the selected version's importer options and inspect errors
before enabling any writers. The export is not a full infrastructure backup.

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

Pause consumption/automation and stop every writer before preserving the entire
`/mnt/SSD/Containers/paperless` tree consistently with original images/settings.
Use the [shared cold restore procedure](../README.md#backing-up-data) and the
[PostgreSQL 18 migration runbook](POSTGRESQL-18-UPGRADE.md). Start
PostgreSQL/broker before the web app, and verify login, document downloads,
metadata and the sanity checker before resuming consumption. Restore exports
only into a deliberately fresh compatible instance; do not import over live
production data. Published host port 8010 bypasses Traefik restrictions.
