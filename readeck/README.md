# Readeck

Self-hosted read-later app. Save articles, pages, and links from any device; Readeck strips away the noise and stores a clean readable copy so the content survives link rot. Supports tagging, highlights, annotations, full-text search, and an RSS feed of your saved items.

Run it when you want a Pocket/Instapaper replacement that keeps your reading list on your own infrastructure.

Images in `compose.yaml` are frozen to the inventoried builds. See the [image update guide](../README.md#image-updates); `docker compose pull` alone does not upgrade them.

## Architecture

```text
Browser / mobile / browser extension
            │
            ▼
      Traefik (TLS)
            │
            ▼
    readeck:8000 (Go)
            │
            ▼
    /readeck (SQLite + article data)
```

Single container — Readeck bundles SQLite so no separate database service is needed.

## Prerequisites

Run Linux/Bash commands from `readeck/`; deploy Traefik first to create
`traefik`. Host CLI work needs the deployed project's private settings.

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

Pause automation and retain original settings/images separately. Set `BACKUP_ROOT`
to an existing private directory outside the checkout and source tree. Run the
whole block; it stops SQLite/article writers and does not resume on failure.

```bash
(
  set -euo pipefail
  umask 077
  root="$(realpath -e "${BACKUP_ROOT:?Set a private backup directory}")"
  state="$(realpath -e /mnt/SSD/Containers/readeck)"
  test ! -L "$state/data"
  test -n "$(find "$state/data" -mindepth 1 -print -quit)"
  checkout="$(realpath ..)"
  case "$root/" in
    "$state/"*|"$checkout/"*) printf "Unsafe backup destination.\n" >&2; exit 1 ;;
  esac
  backup="$(mktemp -d "$root/readeck.XXXXXX")"
  cp -- compose.yaml .env.example "$backup/"
  docker compose stop
  tar --acls --xattrs --numeric-owner --exclude=.zfs \
    -czf "$backup/state.tar.gz" -C "$state" data
  tar -tzf "$backup/state.tar.gz" > /dev/null
  (cd "$backup"; sha256sum compose.yaml .env.example state.tar.gz > SHA256SUMS)
  touch "$backup/COMPLETE"
  printf "Checked local backup: %s\n" "$backup"
  docker compose start
)
```

### Restore

Use the same image/settings on an isolated recovery host with Traefik prepared.
Block client ingress and pause automation. Set `RESTORE_DIR` to a trusted backup
created above. Checksums detect corruption, not authenticity. This example
refuses symlinks and dataset mount points; use TrueNAS snapshot/clone recovery for
datasets. Run the complete fail-fast block, with administrative archive access.

```bash
(
  set -euo pipefail
  umask 077
  state=/mnt/SSD/Containers/readeck
  test "$(realpath -m "$state")" = "$state"
  backup="$(realpath -e "${RESTORE_DIR:?Set the trusted backup directory}")"
  case "$backup/" in "$state/"*) printf "Backup is inside the restore target.\n" >&2; exit 1 ;; esac
  test -f "$backup/COMPLETE"
  (cd "$backup"; sha256sum -c SHA256SUMS)
  cmp -- compose.yaml "$backup/compose.yaml"
  mounts="$(findmnt --list --noheadings --output TARGET)"
  while IFS= read -r path; do
    case "$path" in "$state"|"$state/"*) printf "Use dataset recovery for %s.\n" "$path" >&2; exit 1 ;; esac
  done <<< "$mounts"
  docker compose stop
  if [ -e "$state" ]; then
    old="$state.pre-restore-$(date -u +%Y%m%dT%H%M%SZ)"
    test ! -e "$old"
    mv -- "$state" "$old"
  fi
  mkdir -m 700 -- "$state"
  tar --same-owner --acls --xattrs -xzf "$backup/state.tar.gz" -C "$state"
  test -d "$state/data"
  test ! -L "$state/data"
  test -n "$(find "$state/data" -mindepth 1 -print -quit)"
  docker compose up -d --no-deps --pull never app
)
```

Verify login, bookmarks and article contents before reopening ingress. If a stage
Inventory symlinks first: archives preserve links, not external target data.
Back those targets up separately with every writer stopped. If a stage
fails, leave the stack stopped. For rollback stop containers, retain the failed
tree and reinstate the original tree/settings/images without merging trees.
Keep old data and the backup until accepted. This is not a live-tested restore;
see [shared backup limitations](../README.md#backing-up-data).
