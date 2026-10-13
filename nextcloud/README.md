# Nextcloud

Self-hosted file sync and collaboration platform — private alternative to Google Drive / Dropbox. Includes calendar (CalDAV), contacts (CardDAV), photo gallery, and 500+ installable apps.

Images in `compose.yaml` are frozen to the inventoried builds. See the [image update guide](../README.md#image-updates); `docker compose pull` alone does not upgrade them.

## Services

| Service | Port | Description |
|---|---|---|
| app | 80 internally; `${NEXTCLOUD_PORT:-8020}` on host | Nextcloud web UI and API (proxied via Traefik) |
| db | internal | MariaDB 11 — document metadata and state |
| redis | internal | Redis 7 — file locking and distributed cache |
| cron | internal | Background job runner (replaces system cron) |

`db`, `redis`, and `cron` are on an isolated `nextcloud` bridge network. Only `app` is connected to the `traefik` network.

## Prerequisites

These commands are for **Bash on the TrueNAS/Linux Docker host**, not PowerShell.
Run them from the `nextcloud` directory containing the deployed `compose.yaml`.
Traefik must already have created the external `traefik` network.

### 1. Create storage directories

For a **new installation only**, create the directories below. Do not recursively
change ownership of an existing or restored installation: preserve its numeric
owners and ACLs, especially the database and Redis directories.

```bash
mkdir -p /mnt/SSD/Containers/nextcloud/{html,data,db,redis}
chown -R 33:33 /mnt/SSD/Containers/nextcloud/html
chown -R 33:33 /mnt/SSD/Containers/nextcloud/data
# db and redis are managed internally by their containers — do not chown
```

> **Note:** Nextcloud runs as `www-data` (uid 33) inside the container. `html` and `data` must be owned by uid 33 or the container will fail on first run. You do not need to create a user with uid 33 on TrueNAS — Linux permissions work by numeric uid/gid, so `chown 33:33` sets the correct ownership at the filesystem level without a matching local account.

### 2. Set secrets

```bash
cp .env.example .env
```

The template contains **replacement placeholders**, not generated passwords.
For a new installation, generate a different strong password for each of
`NEXTCLOUD_DB_ROOT_PASSWORD`, `NEXTCLOUD_DB_PASSWORD`,
`NEXTCLOUD_REDIS_PASSWORD`, and `NEXTCLOUD_ADMIN_PASSWORD`; set the domain too.
Keep the resulting settings out of Git. For Portainer, enter the values as
stack variables instead of assuming it reads the host's `.env`.

For an existing installation or restore, retain the original settings from
your protected backup. Changing initialization variables does not rotate
existing database accounts, and new settings may disagree with `config.php`.

## Quick Start

```bash
docker compose up -d
docker compose logs -f app
```

First startup takes 60–90 seconds while Nextcloud initialises the database and creates the admin account. Navigate to `https://<NEXTCLOUD_DOMAIN>` and log in with your admin credentials.

> **Note:** `NEXTCLOUD_ADMIN_USER` / `NEXTCLOUD_ADMIN_PASSWORD` only create the account on the very first run. After that, manage users through the web UI.

## Configuration

`.env` variables:

| Variable | Required | Description |
|---|---|---|
| `NEXTCLOUD_DB_ROOT_PASSWORD` | Yes | MariaDB root password (internal use only) |
| `NEXTCLOUD_DB_PASSWORD` | Yes | MariaDB password for the nextcloud app user |
| `NEXTCLOUD_REDIS_PASSWORD` | Yes | Redis auth password |
| `NEXTCLOUD_ADMIN_USER` | Yes | Initial admin username (first run only) |
| `NEXTCLOUD_ADMIN_PASSWORD` | Yes | Initial admin password (first run only) |
| `NEXTCLOUD_DOMAIN` | Yes | Hostname Traefik routes to Nextcloud |
| `NEXTCLOUD_PORT` | No | Host port for direct access (default: `8020`) |

## Storage

| Data | Host Path |
|---|---|
| Application files, `config/config.php`, custom apps, themes | `/mnt/SSD/Containers/nextcloud/html` |
| User files, encryption material stored with those files, logs | `/mnt/SSD/Containers/nextcloud/data` |
| MariaDB data | `/mnt/SSD/Containers/nextcloud/db` |
| Redis data | `/mnt/SSD/Containers/nextcloud/redis` |

## Proxy Notes

The compose file sets three environment variables that configure Nextcloud to work correctly behind Traefik:

- `OVERWRITEPROTOCOL=https` — tells Nextcloud all requests arrive over HTTPS
- `OVERWRITECLIURL` — sets the canonical URL for CLI commands and notifications
- `TRUSTED_PROXIES` — whitelists the Docker network ranges so `X-Forwarded-For` headers are trusted

A Traefik redirect middleware (`nextcloud-dav`) rewrites `.well-known/carddav` and `.well-known/caldav` to `/remote.php/dav` so desktop and mobile clients can auto-discover CalDAV/CardDAV.

## Administration (`occ`)

Run all `occ` commands as uid 33 (`www-data`):

```bash
docker compose exec -u 33 app php occ <command>
```

### Common commands

```bash
# Check server status and warnings
docker compose exec -u 33 app php occ status
docker compose exec -u 33 app php occ check

# Rescan files (after adding files directly to the data directory)
docker compose exec -u 33 app php occ files:scan --all

# Fix database warnings (run after upgrades)
docker compose exec -u 33 app php occ db:add-missing-indices
docker compose exec -u 33 app php occ db:add-missing-columns
docker compose exec -u 33 app php occ db:convert-filecache-bigint

# Maintenance mode
docker compose exec -u 33 app php occ maintenance:mode --on
docker compose exec -u 33 app php occ maintenance:mode --off

# Tail the application log
docker compose exec -u 33 app php occ log:tail -f
```

## Maintenance

### Update images

Review the selected release and app/database compatibility, take a complete
backup, and update both the tag and digest for `app` **and** `cron` together
before these commands. A pull alone does not advance the pinned images.

```bash
docker compose pull
docker compose up -d
docker compose logs -f app   # watch for upgrade output
```

> **Upgrade rule:** Nextcloud only supports one major version at a time; do not skip majors. `up -d` can run entrypoint migrations when the selected image changes. A restore is not an upgrade: first recover with the backed-up image versions.

### Post-upgrade cleanup

```bash
docker compose exec -u 33 app php occ db:add-missing-indices
docker compose exec -u 33 app php occ db:add-missing-columns
docker compose exec -u 33 app php occ db:add-missing-primary-keys
```

### Backup

This procedure backs up **the application files and user data plus a logical
MariaDB dump**. It stops `app` and `cron` while collecting both parts, so plan
an outage long enough for the dump and archive. Redis is a cache/lock store,
not the authoritative copy of Nextcloud data; recovery uses a fresh Redis
directory. Do not copy a running MariaDB data directory as a substitute for the
dump.

Before starting:

- Start from a working, installed instance with maintenance mode off. Do not
  use this normal-operation backup/resume sequence during an unfinished
  installation, upgrade, or recovery.
- Before downtime, confirm the host CLI supports `start --wait`,
  `--wait-timeout`, and `up --pull never` using its `start --help` and
  `up --help` output. These examples also require GNU tar/coreutils/sed and
  `findmnt`; the local Windows CLI does not establish host compatibility.
- Pause Portainer updates and any other automation that could recreate these
  containers. Allow active uploads/jobs to finish. Confirm the CLI uses the
  deployed Compose project name and the local Docker daemon; Portainer settings
  are not automatically available to host CLI commands.
- Confirm the unrendered Compose file describes the **running** images. Retain
  those images for recovery; do not pull or upgrade just to take a backup.
- Securely retain the matching `.env` or Portainer variables in an encrypted
  backup/password manager. They are not included by the commands below.
- Use an existing, private backup directory outside both the source data and
  this checkout. Set the shell variable `NEXTCLOUD_BACKUP_ROOT` to that directory.
  It is a backup-helper setting, not a Compose variable. Have sufficient free
  space and administrative access to read all files and preserve ownership.
  The example expects real `html`/`data` directories, not symlinks; extend the
  procedure for any symlink targets outside these directories.

The restore set is:

| Backup component | Required contents |
|---|---|
| `files.tar.gz` | Entire `html` and `data` directories, including `html/config`, custom apps, themes, and file encryption material |
| `database.sql` | Nextcloud database tables and associated routines/events/triggers |
| Deployment metadata | Unrendered `compose.yaml`, template, image listing, and Nextcloud status/version |
| Separately protected settings | Original credentials and stack variables matching the database and `config.php` |
| Additional storage, if configured | External storage contents, external keys/configuration, and any other mounts not in this base stack |

The archive and SQL contain private data and potentially credentials. Protect
them with restrictive permissions and encryption before any off-host transfer;
keep a verified copy on separate storage. A local archive or same-pool snapshot
alone is not protection against loss of that pool. Retain TrueNAS dataset
properties, encryption recovery material, and NFSv4 ACL configuration separately;
GNU tar's ACL/xattr options are not a complete ZFS dataset backup.

Run the following **whole subshell**, not selected lines. It stops on failure
and does not automatically restart services after an error. Never enable shell
tracing (`set -x`) for credential-handling commands.

```bash
(
  set -euo pipefail
  umask 077
  trap 'printf "Backup/resume failed. Stop here; inspect services and maintenance mode before continuing.\n" >&2' ERR
  state="$(realpath -e /mnt/SSD/Containers/nextcloud)"
  parent="$(realpath -e "${NEXTCLOUD_BACKUP_ROOT:?Set an existing private backup directory}")"
  checkout="$(realpath ..)"
  case "$parent/" in
    "$state/"*|"$checkout/"*) printf "Backup destination must be outside data and checkout.\n" >&2; exit 1 ;;
  esac
  test -d "$parent"
  test -d "$state/html"
  test -d "$state/data"
  if [ -L "$state/html" ] || [ -L "$state/data" ]; then
    printf "Symlinked html/data need a separately reviewed backup procedure.\n" >&2
    exit 1
  fi
  test -s "$state/html/config/config.php"
  docker compose config --quiet
  backup="$(mktemp -d "$parent/nextcloud-$(date -u +%Y%m%dT%H%M%SZ).XXXXXX")"
  cp -- compose.yaml .env.example "$backup/"
  docker compose images > "$backup/images.txt"
  docker compose exec -T -u 33 app php occ status --output=json > "$backup/nextcloud-status.json"

  docker compose exec -T -u 33 app php occ maintenance:mode --on
  docker compose stop -t 60 cron app
  docker compose exec -T db sh -eu -c '
    umask 077
    auth="$(mktemp)"
    trap '\''rm -f -- "$auth"'\'' EXIT
    password="$(printf "%s" "${MYSQL_PASSWORD:?}" |
      sed -z -e '\''s/\\/\\\\/g'\'' -e '\''s/"/\\"/g'\'' \
             -e '\''s/\n/\\n/g'\'' -e '\''s/\r/\\r/g'\'' -e '\''s/\t/\\t/g'\'')"
    printf "[client]\npassword=\"%s\"\n" "$password" > "$auth"
    mariadb-dump --defaults-file="$auth" --user="${MYSQL_USER:?}" \
      --single-transaction --skip-lock-tables --default-character-set=utf8mb4 \
      --routines --events --triggers --no-tablespaces "${MYSQL_DATABASE:?}"
  ' > "$backup/database.sql"
  test -s "$backup/database.sql"
  tar --acls --xattrs --numeric-owner --exclude=.zfs \
    -czf "$backup/files.tar.gz" -C "$state" html data
  tar -tzf "$backup/files.tar.gz" > /dev/null
  (
    cd "$backup"
    sha256sum compose.yaml .env.example images.txt nextcloud-status.json \
      database.sql files.tar.gz > SHA256SUMS
    sha256sum -c SHA256SUMS
    touch COMPLETE
  )
  printf "Backup checks completed: %s\n" "$backup"

  docker compose start --wait --wait-timeout 120 app
  docker compose exec -T -u 33 app php occ maintenance:mode --off
  docker compose start cron
)
```

The temporary client option file keeps the password out of client arguments
and is removed on exit. Its values come from the `db` container's existing
environment, not unexported host-shell `.env` variables. `-T` prevents a TTY
from contaminating redirected output. MariaDB 11's official image removed the
`mysqldump` alias; use `mariadb-dump` and the compatible `mariadb` import client.

Only a directory with `COMPLETE` has passed these dump/archive/checksum checks.
This is **not proof of recoverability**; perform an isolated restore drill.
If a command fails, keep the partial backup separate, inspect which services
are stopped and whether maintenance mode is still on, and resolve the cause
before resuming them. Re-enable update automation only after normal operation
is confirmed.

### Restore from backup

**Test on an isolated recovery host first.** Use the backed-up image pins and
original settings, not today's latest images. Keep clients, Traefik ingress,
and the published host port blocked during recovery; `lan-only` does not block
LAN sync clients or direct-port access. Pause deployment automation.

Before downtime, verify a trusted backup's `COMPLETE`, checksums, archive
listing, and availability of its separately retained settings. Checksums detect
corruption, not authenticity: do not extract untrusted archives. Copy the
backed-up unrendered Compose file/template into a separate private deployment
directory, securely restore its CLI settings (or matching Portainer variables),
and select the correct project name. Prepare the external `traefik` network
through its owning stack on the recovery host.

**Preserve the current installation and its Compose/settings/images for
rollback.** The directory-renaming example below is only for ordinary
directories. It refuses ZFS dataset mount points; for dataset-backed paths,
use supported TrueNAS snapshots/clones to retain the originals and prepare
fresh destinations at the configured paths. Do not rename mount points or
extract over live/original datasets. Once fresh destinations are prepared,
the same archive extraction and staged database/app recovery apply.

Set the shell variable `NEXTCLOUD_RESTORE_DIR` to the verified backup directory.
The following stage stops the stack, preserves its old tree when present,
restores files, and imports SQL into a **fresh, empty database**. It deliberately
leaves maintenance mode enabled and `cron` stopped.

```bash
(
  set -euo pipefail
  umask 077
  trap 'printf "Restore failed. Keep clients blocked and cron stopped; do not initialize or overwrite more data.\n" >&2' ERR
  if [ -L /mnt/SSD/Containers/nextcloud ]; then
    printf "Do not replace a symlinked data tree with this directory procedure.\n" >&2
    exit 1
  fi
  state="$(realpath -m /mnt/SSD/Containers/nextcloud)"
  backup="$(realpath -e "${NEXTCLOUD_RESTORE_DIR:?Set the verified backup directory}")"
  case "$backup/" in
    "$state/"*) printf "Restore source must be outside the data tree.\n" >&2; exit 1 ;;
  esac
  test -f "$backup/COMPLETE"
  (cd "$backup"; sha256sum -c SHA256SUMS)
  test -s "$backup/database.sql"
  tar -tzf "$backup/files.tar.gz" > /dev/null
  cmp -- compose.yaml "$backup/compose.yaml"
  docker compose config --quiet
  mounts="$(findmnt --list --noheadings --output TARGET)"
  while IFS= read -r path; do
    case "$path" in
      "$state"|"$state/"*)
        printf "Mount point detected: %s. Use the TrueNAS recovery workflow instead.\n" "$path" >&2
        exit 1 ;;
    esac
  done <<< "$mounts"

  docker compose down
  if [ -e "$state" ]; then
    rollback="$state.pre-restore-$(date -u +%Y%m%dT%H%M%SZ)"
    test ! -e "$rollback"
    mv -- "$state" "$rollback"
    printf "Preserved original tree: %s\n" "$rollback"
  fi
  mkdir -m 700 -- "$state"
  mkdir -- "$state/db" "$state/redis"
  tar --same-owner --acls --xattrs -xzf "$backup/files.tar.gz" -C "$state"
  test -s "$state/html/config/config.php"
  test -d "$state/data"
  docker compose up -d --no-deps --wait --wait-timeout 120 --pull never db redis
  docker compose exec -T db sh -eu -c '
    umask 077
    auth="$(mktemp)"
    trap '\''rm -f -- "$auth"'\'' EXIT
    password="$(printf "%s" "${MYSQL_PASSWORD:?}" |
      sed -z -e '\''s/\\/\\\\/g'\'' -e '\''s/"/\\"/g'\'' \
             -e '\''s/\n/\\n/g'\'' -e '\''s/\r/\\r/g'\'' -e '\''s/\t/\\t/g'\'')"
    printf "[client]\npassword=\"%s\"\n" "$password" > "$auth"
    tables="$(mariadb --defaults-file="$auth" --user="${MYSQL_USER:?}" \
      --database="${MYSQL_DATABASE:?}" --batch --skip-column-names \
      --execute="SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE()")"
    if [ "$tables" != 0 ]; then
      printf "Refusing to import into a non-empty database.\n" >&2
      exit 1
    fi
    mariadb --defaults-file="$auth" --user="$MYSQL_USER" --database="$MYSQL_DATABASE"
  ' < "$backup/database.sql"
  docker compose up -d --no-deps --wait --wait-timeout 120 --pull never app
  docker compose exec -T -u 33 app php occ maintenance:mode --on
  docker compose exec -T -u 33 app php occ status --output=json
)
```

Never use `down -v`, delete the old directories, or drop a used database to
make a failed restore continue. If extraction or import fails, leave the
application unavailable and preserve the failed restore separately for diagnosis.
To roll back, stop the recovery containers, retain their directories, restore
the original directory tree or dataset snapshots, and reinstate the original
Compose pins/settings. Do not merge old and restored trees.

Before allowing users back, compare `occ status` with `nextcloud-status.json`:
the installation/version must match and `needsDbUpgrade` must be false.
Preserve the archive's numeric ownership/ACLs; do not recursively chown
database/Redis data to `33:33`. Investigate startup errors before continuing.

If clients changed files after the backup, review Nextcloud's
[post-recovery synchronization guidance](https://docs.nextcloud.com/server/34/admin_manual/maintenance/restore.html#synchronising-with-clients-after-data-recovery)
and decide whether `maintenance:data-fingerprint` is needed **before** clients
reconnect. It can cause conflicts and is not a routine restore step.
Do not run `files:scan --all` by default; a consistent database/files restore
should not need a rebuild, and scans do not replace restoration of database
metadata.

With ingress still restricted to the recovery operator, disable maintenance:

```bash
docker compose exec -T -u 33 app php occ maintenance:mode --off
```

Verify login, representative downloads/uploads, calendars/contacts, installed
apps, and decryption if enabled. If verification fails, keep clients blocked
and re-enable maintenance mode before investigating. Only after verification,
start background jobs with the same frozen image:

```bash
docker compose up -d --no-deps --pull never cron
docker compose ps
```

Then restore normal client access/update automation. Retain the old data and
validated backup until the recovery is accepted; this README has not been
verified by a live restore drill.

References checked on **2026-10-12**:
[Nextcloud 34 backup](https://docs.nextcloud.com/server/34/admin_manual/maintenance/backup.html),
[Nextcloud 34 restore](https://docs.nextcloud.com/server/34/admin_manual/maintenance/restore.html),
and [MariaDB dump/client compatibility](https://mariadb.com/docs/server/clients-and-utilities/backup-restore-and-import-clients/mariadb-dump).
