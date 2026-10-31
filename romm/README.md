# RomM

RomM (ROM Manager) is a self-hosted game library manager with a slick web UI. It scans your ROM collection, fetches metadata and artwork from multiple sources (ScreenScraper, RetroAchievements, SteamGridDB, IGDB), and gives you a searchable, filterable library across any platform — from NES to PS5.

Run it when you want a Plex-style experience for your game collection: clean cover art, descriptions, release dates, and the ability to browse by platform, genre, or franchise from any device on your LAN.

Images in `compose.yaml` are frozen to the inventoried builds. See the [image update guide](../README.md#image-updates); `docker compose pull` alone does not upgrade them.

## Architecture

```text
Browser
  │
  ▼
Traefik (TLS termination, lan-only)
  │
  ▼
romm:8080  ──── embedded Redis/Valkey (session/cache)
  │
  ▼
romm-db:3306  (MariaDB LTS)
```

RomM ships with an embedded Redis/Valkey instance for session management and caching — no separate Redis container is needed. The Redis data volume must be mounted at `/redis-data`, which is where the current RomM image writes its embedded Redis snapshots. The ROM library at `/mnt/Data/Media/ROMs` is mounted read-only from RomM's perspective but can be written to by other processes on the host.

Read-only library mounting prevents RomM uploads, deletion, or reorganization of ROM files. Manage those files on the host, then rescan. Existing deployments become read-only when this Compose change is explicitly redeployed.

## Prerequisites

### 1. Create host directories

```bash
mkdir -p /mnt/SSD/Containers/romm/{resources,redis-data,assets,config,db}
# Fresh app paths only; do not change MariaDB's ownership
chown -R 3001:3001 /mnt/SSD/Containers/romm/{resources,redis-data,assets,config}
```

The ROM library must already exist and grant UID/GID 3001 read/traverse access
through its existing ACLs; do not recursively change ownership of shared media.
Deploy Traefik first and run Linux/Bash examples from `romm/`.

### 2. Organize your ROM library

RomM expects ROMs grouped into platform folders using RetroArch-style slugs:

```text
/mnt/Data/Media/ROMs/
├── gba/
├── gbc/
├── gb/
├── nes/
├── snes/
├── n64/
├── nds/
├── ps/
├── ps2/
├── psp/
└── ...
```

Consult the [official RomM documentation](https://docs.romm.app/latest/) for the folder structure supported by your selected release. Folders that don't match a known slug can require manual platform mapping in the UI.

### 3. Generate an auth secret key

```bash
openssl rand -hex 32
```

Paste the output into `ROMM_AUTH_SECRET_KEY` in your `.env`.

## Quick Start

```bash
# 1. Fill in your secrets
cp .env.example .env
$EDITOR .env

# 2. Start the stack
docker compose up -d

# 3. Watch logs until healthy
docker compose logs -f
```

Navigate to `https://${ROMM_DOMAIN}` — RomM will prompt you to create your first admin user on first launch.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ROMM_DOMAIN` | Yes | Traefik domain for the web UI |
| `ROMM_AUTH_SECRET_KEY` | Yes | Random 32+ byte hex string for session signing (`openssl rand -hex 32`) |
| `ROMM_DB_USER` | Yes | MariaDB username (default: `romm-user`) |
| `ROMM_DB_PASSWORD` | Yes | MariaDB user password |
| `ROMM_DB_ROOT_PASSWORD` | Yes | MariaDB root password |
| `SCREENSCRAPER_USER` | No | ScreenScraper.fr account username |
| `SCREENSCRAPER_PASSWORD` | No | ScreenScraper.fr account password |
| `RETROACHIEVEMENTS_API_KEY` | No | RetroAchievements API key |
| `STEAMGRIDDB_API_KEY` | No | SteamGridDB API key |

`HASHEOUS_API_ENABLED` is hardcoded to `true` in compose — Hasheous requires no account and is always enabled.

## Scraper API Keys

All scrapers are optional. RomM will still work without them but won't pull metadata or artwork.

| Scraper | Purpose | Get a key |
|---|---|---|
| ScreenScraper | Primary metadata + artwork for most platforms | [screenscraper.fr](https://www.screenscraper.fr/membreinscription.php) — free account |
| RetroAchievements | Achievement data and game hashing | [retroachievements.org](https://retroachievements.org/createaccount.php) → Settings → API Key |
| SteamGridDB | Additional grid/banner artwork | [steamgriddb.com](https://www.steamgriddb.com/profile/preferences/api) — free account |

Add keys to `.env` and `docker compose up -d` to reload — no rebuild needed.

## Volumes

| Mount | Host Path | Purpose |
|---|---|---|
| `/romm/resources` | `/mnt/SSD/Containers/romm/resources` | Scraped metadata and cover art cache |
| `/redis-data` | `/mnt/SSD/Containers/romm/redis-data` | Embedded Redis/Valkey persistence |
| `/romm/library` | `/mnt/Data/Media/ROMs` | ROM files (read by RomM, organized by platform slug) |
| `/romm/assets` | `/mnt/SSD/Containers/romm/assets` | User-uploaded assets (custom artwork, etc.) |
| `/romm/config` | `/mnt/SSD/Containers/romm/config` | RomM config file (`config.yml`) |
| `/var/lib/mysql` | `/mnt/SSD/Containers/romm/db` | MariaDB data directory |

## Notes

- **RomM `5.4.0` and MariaDB `12.3.3` are pinned with verified digests to the already-running images.** Replacing the old `mariadb:lts` reference does not select a newer database. Before future updates, review migrations and back up the complete restore set. Never change an existing database major without its supported migration procedure.
- **Port 8080** is RomM's internal container port — no host port is exposed, Traefik handles all routing.
- **`restart: true`** in `depends_on` restarts RomM after explicit Compose-controlled database updates/restarts; it does not propagate automatic container-runtime restarts.
- **Redis/Valkey writes to `/redis-data`**. If this is mounted elsewhere, Docker may create an anonymous volume at `/redis-data`; the embedded Redis process can then fail snapshot persistence and raise `MISCONF` / `stop-writes-on-bgsave-error` errors.

## Recovery

Check both services/logs and verify login plus a known game's assets. Stop
app/database writers before preserving all five SSD directories, original auth
secret, DB/API credentials and image pins. Back up irreplaceable ROMs separately,
coordinating any other writers despite this app's read-only mount. Use the
[shared recovery procedure](../README.md#backing-up-data), retain numeric owners,
start the compatible database before the app, and verify games/artwork/login
before rescanning. Do not enable a metadata scan to mask missing restored data.
