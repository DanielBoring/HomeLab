# RomM

RomM (ROM Manager) is a self-hosted game library manager with a slick web UI. It scans your ROM collection, fetches metadata and artwork from multiple sources (ScreenScraper, RetroAchievements, SteamGridDB, IGDB), and gives you a searchable, filterable library across any platform — from NES to PS5.

Run it when you want a Plex-style experience for your game collection: clean cover art, descriptions, release dates, and the ability to browse by platform, genre, or franchise from any device on your LAN.

## Architecture

```
Browser
  │
  ▼
Traefik (TLS termination, lan-only)
  │
  ▼
romm:8080  ──── embedded Redis (session/cache)
  │
  ▼
romm-db:3306  (MariaDB LTS)
```

RomM ships with an embedded Redis instance for session management and caching — no separate Redis container is needed. The ROM library at `/mnt/Data/Media/ROMs` is mounted read-only from RomM's perspective but can be written to by other processes on the host.

## Prerequisites

### 1. Create host directories

```bash
mkdir -p /mnt/SSD/Containers/romm/{resources,redis-data,assets,config,db}
chown -R 3001:3001 /mnt/SSD/Containers/romm
```

The ROM library at `/mnt/Data/Media/ROMs` should already exist and be owned by 3001:3001.

### 2. Organize your ROM library

RomM expects ROMs grouped into platform folders using RetroArch-style slugs:

```
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

See the [full platform slug list](https://docs.romm.app/latest/ROMs-Management/Folder-Structure/) in the RomM docs. Folders that don't match a known slug are shown as "unknown platform" and can be manually mapped in the UI.

### 3. Generate an auth secret key

```bash
openssl rand -hex 32
```

Paste the output into `ROMM_AUTH_SECRET_KEY` in your `.env`.

## Quick Start

```bash
# 1. Fill in your secrets
cp example.env .env
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
| `/romm/redis-data` | `/mnt/SSD/Containers/romm/redis-data` | Embedded Redis persistence |
| `/romm/library` | `/mnt/Data/Media/ROMs` | ROM files (read by RomM, organized by platform slug) |
| `/romm/assets` | `/mnt/SSD/Containers/romm/assets` | User-uploaded assets (custom artwork, etc.) |
| `/romm/config` | `/mnt/SSD/Containers/romm/config` | RomM config file (`config.yml`) |
| `/var/lib/mysql` | `/mnt/SSD/Containers/romm/db` | MariaDB data directory |

## Notes

- **mariadb:lts** is used instead of `mariadb:latest` — pinning to the LTS tag avoids surprise major-version upgrades that require manual data migration steps. Update intentionally with `docker compose pull` when you're ready.
- **Port 8080** is RomM's internal container port — no host port is exposed, Traefik handles all routing.
- **`restart: true`** in `depends_on` means Docker will restart RomM if MariaDB restarts, re-establishing the DB connection automatically.
