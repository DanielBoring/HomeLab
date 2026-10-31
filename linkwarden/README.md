# Linkwarden

Self-hosted bookmark manager. Saves links with full-page snapshots, PDFs, and readable text archives so bookmarks survive link rot. Supports collections, tags, and sharing — works as a team tool or a personal read-later list.

Run it when you want bookmarks that outlast the pages they point to and don't live in a browser profile tied to one machine.

Images in `compose.yaml` are frozen to the inventoried builds. See the [image update guide](../README.md#image-updates); `docker compose pull` alone does not upgrade them.

## Architecture

```text
Browser / API clients
        │
        ▼
   Traefik (TLS)
        │
        ▼
  linkwarden:3000  ──── linkwarden-db (PostgreSQL 16)
        │
        ▼
  /data/data  (screenshots, PDFs, archives)
```

| Service | Port | Description |
|---|---|---|
| app | 3000 | Next.js web UI and REST API (proxied via Traefik) |
| db | internal | PostgreSQL 16 — all bookmark metadata and user data |

`db` is on an isolated `linkwarden` bridge network. Only `app` is connected to the `traefik` network.

## Prerequisites

Run Linux/Bash commands from `linkwarden/`; deploy Traefik first to create
`traefik`. Use matching Portainer settings/project identity for host CLI work.

### 1. Create storage directories

```bash
mkdir -p /mnt/SSD/Containers/linkwarden/{db,data}
```

PostgreSQL and the app use image-specific users. Verify access at the selected
version; do not assume fresh directories or restored ACLs always need no
preparation, and never blanket-chown the database to the app's UID.

### 2. Generate secrets

```bash
# Postgres password — must be hex; base64 contains +/= which break the DATABASE_URL
openssl rand -hex 32

# NextAuth secret
openssl rand -base64 32
```

Paste the outputs into `.env`.

## Quick Start

```bash
cp .env.example .env
# Edit .env — fill in LINKWARDEN_DOMAIN, POSTGRES_PASSWORD, NEXTAUTH_SECRET
docker compose up -d
docker compose logs -f app
```

First startup runs database migrations automatically. Navigate to `https://<LINKWARDEN_DOMAIN>` and create your account — the first registered user becomes admin.

> **Note:** Registration is open by default. After creating the owner account,
> deliberately add `NEXT_PUBLIC_DISABLE_REGISTRATION=true` to `app.environment`
> in Compose and recreate the app for a personal instance. Adding it only to
> `.env` does not pass it through this base stack. Preserve a tested owner login.

## Configuration

| Variable | Required | Description |
|---|---|---|
| `LINKWARDEN_DOMAIN` | Yes | Hostname Traefik routes to Linkwarden |
| `TZ` | No | Timezone (default: `America/New_York`) |
| `POSTGRES_USER` | Yes | PostgreSQL username |
| `POSTGRES_PASSWORD` | Yes | PostgreSQL password — use URL-safe `openssl rand -hex 32` |
| `POSTGRES_DB` | Yes | PostgreSQL database name |
| `NEXTAUTH_SECRET` | Yes | NextAuth signing secret — generate with `openssl rand -base64 32` |

`DATABASE_URL` and `NEXTAUTH_URL` are derived automatically in `compose.yaml` from the above variables — do not add them to `.env`.

`NEXTAUTH_URL` includes `/api/v1/auth`, matching the
[v2.16.3 upstream environment sample](https://github.com/linkwarden/linkwarden/blob/v2.16.3/.env.sample)
(checked 2026-10-13). The browser UI remains at the domain root. Review any
external provider callback settings against that path before redeployment.

## Storage

| Data | Host Path |
|---|---|
| Screenshots, PDFs, readable archives | `/mnt/SSD/Containers/linkwarden/data` |
| PostgreSQL data | `/mnt/SSD/Containers/linkwarden/db` |

## Maintenance

### Update images

```bash
docker compose pull
docker compose up -d
docker compose logs -f app
```

### Backup

Pause deployment automation; store original settings encrypted separately.
Set `BACKUP_ROOT` to an existing private directory outside the checkout and
`/mnt/SSD/Containers/linkwarden`. Run the whole Linux/Bash block. It stops all
writers before copying database files; failures leave the stack stopped.

```bash
(
  set -euo pipefail
  umask 077
  root="$(realpath -e "${BACKUP_ROOT:?Set a private backup directory}")"
  state="$(realpath -e /mnt/SSD/Containers/linkwarden)"
  test ! -L "$state/db"
  test ! -L "$state/data"
  test -s "$state/db/PG_VERSION"
  checkout="$(realpath ..)"
  case "$root/" in
    "$state/"*|"$checkout/"*) printf "Unsafe backup destination.\n" >&2; exit 1 ;;
  esac
  backup="$(mktemp -d "$root/linkwarden.XXXXXX")"
  cp -- compose.yaml .env.example "$backup/"
  docker compose stop
  tar --acls --xattrs --numeric-owner --exclude=.zfs \
    -czf "$backup/state.tar.gz" -C "$state" db data
  tar -tzf "$backup/state.tar.gz" > /dev/null
  (cd "$backup"; sha256sum compose.yaml .env.example state.tar.gz > SHA256SUMS)
  touch "$backup/COMPLETE"
  printf "Checked local backup: %s\n" "$backup"
  docker compose start
)
```

### Restore

Test an isolated restore first with the original image versions/settings and
the external Traefik network prepared. Block client ingress and pause automation.
Set `RESTORE_DIR` to a trusted backup created above. Do not extract untrusted
archives: checksums detect corruption, not authenticity. This example refuses
symlinked paths and dataset mount points; use TrueNAS snapshot/clone recovery for
datasets rather than renaming mount points.

```bash
(
  set -euo pipefail
  umask 077
  state=/mnt/SSD/Containers/linkwarden
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
  test -d "$state/db"
  test -d "$state/data"
  test ! -L "$state/db"
  test ! -L "$state/data"
  test -s "$state/db/PG_VERSION"
  docker compose up -d --no-deps --wait --wait-timeout 120 --pull never db
  docker compose up -d --no-deps --pull never app
)
```

Preserve numeric ownership; use administrative access for the archive commands.
Inventory symlinks/external tablespaces first; their targets need separate
consistent backups. This recipe rejects symlinked primary data directories,
but does not establish that external linked data was included.
Do not continue after a failed stage or initialize an empty replacement database.
Verify login, collections and archived pages/PDFs before reopening ingress.
For rollback stop containers, retain the failed tree, restore the original tree
and original settings/images, and do not merge trees. Retain both backup and old
data until recovery is accepted. These commands have not been live restore-tested;
see the [shared recovery limitations](../README.md#backing-up-data).
