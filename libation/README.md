# Libation

[Libation](https://getlibation.com) is a headless Audible audiobook manager that periodically scans your Audible library and downloads your purchases as DRM-free audio files (M4B/MP3). It runs as a background daemon with no web UI — once configured it silently keeps your local library in sync.

The typical use case in this homelab is to feed downloaded books directly into the Audiobookshelf library at `/mnt/Data/Media/Audiobooks`.

## Architecture

```
Audible API
    │
    ▼
libation (container)
    │  reads credentials from /config/AccountsSettings.json
    │  writes books to /data  ──────────────────────────────▶ /mnt/Data/Media/Audiobooks
    │  stores metadata in /db
    │
    └── no web UI, no ports, no Traefik — pure background daemon
```

Libation has no web interface. All management happens via configuration files that you place in the config volume before starting the container. After first-run account setup (see below) the container is fully autonomous.

## Prerequisites

- `/mnt/SSD/Containers/libation/config` and `/mnt/SSD/Containers/libation/db` must exist on the host before first start.
- `/mnt/Data/Media/Audiobooks` must exist and be writable by PUID 3001.

```bash
mkdir -p /mnt/SSD/Containers/libation/{config,db}
mkdir -p /mnt/Data/Media/Audiobooks
chown -R 3001:3001 /mnt/SSD/Containers/libation /mnt/Data/Media/Audiobooks
```

## Audible Account Setup

Libation does **not** accept Audible credentials as environment variables. Credentials are stored in `AccountsSettings.json`, which you generate once using the desktop Libation app:

1. Download the [Libation desktop app](https://github.com/rmcrackan/Libation/releases/latest) on any machine.
2. Add your Audible account through the GUI (handles the Audible login challenge).
3. Copy `AccountsSettings.json` from the desktop app's settings directory into `/mnt/SSD/Containers/libation/config/` on the host.
4. Start the container — it will use those credentials on every subsequent scan.

The desktop app's settings directory is typically:
- **Windows:** `%APPDATA%\Libation\`
- **macOS:** `~/Library/Application Support/Libation/`
- **Linux:** `~/.config/Libation/`

## Quick Start

```bash
# 1. Create host directories
mkdir -p /mnt/SSD/Containers/libation/{config,db}
mkdir -p /mnt/Data/Media/Audiobooks
chown -R 3001:3001 /mnt/SSD/Containers/libation /mnt/Data/Media/Audiobooks

# 2. Drop AccountsSettings.json into config (see Account Setup above)

# 3. Copy and fill environment
cp example.env .env   # defaults are fine for most setups

# 4. Start
docker compose up -d

# 5. Tail logs to confirm first scan succeeds
docker compose logs -f
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TZ` | `America/New_York` | Container timezone |
| `PUID` | `3001` | UID the container runs as (via `user:` directive) |
| `PGID` | `3001` | GID the container runs as |
| `SLEEP_TIME` | `6h` | Scan interval. Duration string (`30m`, `6h`, `24h`) or `-1` to run once and exit |

## Volumes

| Mount | Host Path | Purpose |
|---|---|---|
| `/config` | `/mnt/SSD/Containers/libation/config` | `AccountsSettings.json`, `Settings.json` |
| `/db` | `/mnt/SSD/Containers/libation/db` | Libation SQLite database |
| `/data` | `/mnt/Data/Media/Audiobooks` | Downloaded audiobook files |

## Notes

- **No Traefik / no ports** — this service has no web UI. It is not in the port registry.
- **User mapping** — Libation's image defaults to UID 1001. This compose file overrides it with `user: "${PUID}:${PGID}"` to match the rest of the homelab (3001:3001). If you see permission errors, confirm host directory ownership matches.
- **SLEEP_TIME=-1** — use this if you prefer to trigger scans via an external cron job rather than the container's internal loop.
- **PostgreSQL** — the `LIBATION_CONNECTION_STRING` env var (not set here) lets you swap the SQLite database for PostgreSQL if you need multi-instance or remote access to the metadata.
