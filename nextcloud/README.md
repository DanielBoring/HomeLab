# Nextcloud

Self-hosted file sync and collaboration platform — private alternative to Google Drive / Dropbox. Includes calendar (CalDAV), contacts (CardDAV), photo gallery, and 500+ installable apps.

## Services

| Service | Port | Description |
|---|---|---|
| app | 8020 | Nextcloud web UI and API (proxied via Traefik) |
| db | internal | MariaDB 11 — document metadata and state |
| redis | internal | Redis 7 — file locking and distributed cache |
| cron | internal | Background job runner (replaces system cron) |

`db`, `redis`, and `cron` are on an isolated `nextcloud` bridge network. Only `app` is connected to the `traefik` network.

## Prerequisites

### 1. Create storage directories

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
# Edit .env — set NEXTCLOUD_ADMIN_PASSWORD
# DB and Redis passwords are pre-generated
```

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
| Application files (PHP, themes, apps) | `/mnt/SSD/Containers/nextcloud/html` |
| User files, logs, config | `/mnt/SSD/Containers/nextcloud/data` |
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

```bash
docker compose pull
docker compose up -d
docker compose logs -f app   # watch for upgrade output
```

> **Upgrade rule:** Nextcloud only supports one major version at a time (e.g., 30 → 31, not 30 → 32). Pull images and `up -d` — the entrypoint script runs migrations automatically.

### Post-upgrade cleanup

```bash
docker compose exec -u 33 app php occ db:add-missing-indices
docker compose exec -u 33 app php occ db:add-missing-columns
docker compose exec -u 33 app php occ db:add-missing-primary-keys
```

### Backup

```bash
# 1. Enable maintenance mode
docker compose exec -u 33 app php occ maintenance:mode --on

# 2. Database dump
docker compose exec db sh -c 'mysqldump --single-transaction -u nextcloud -p"$MYSQL_PASSWORD" nextcloud' \
  > nextcloud-db-$(date +%Y%m%d).sql

# 3. Data and config
tar -czf nextcloud-data-$(date +%Y%m%d).tar.gz \
  /mnt/SSD/Containers/nextcloud/data

# 4. Disable maintenance mode
docker compose exec -u 33 app php occ maintenance:mode --off
```

### Restore from backup

```bash
# Deploy a fresh instance at the same version, then:
docker compose exec -u 33 app php occ maintenance:mode --on
docker compose exec -i db mysql -u nextcloud -p"${NEXTCLOUD_DB_PASSWORD}" nextcloud < nextcloud-db-backup.sql
# Restore data directory from tar
docker compose exec -u 33 app php occ maintenance:mode --off
docker compose exec -u 33 app php occ maintenance:data-fingerprint
docker compose exec -u 33 app php occ files:scan --all
```
