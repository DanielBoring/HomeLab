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
chown -R 3001:3001 /mnt/SSD/Containers/libation
```

---

## First-Time Setup

The Docker container is headless — it cannot prompt you for your Audible password or handle the login challenge interactively. You **must** complete the account setup using the desktop app first, then copy the resulting config files to the Docker volume. This only needs to happen once.

### Step 1 — Install the Desktop App

Download the latest release from [GitHub](https://github.com/rmcrackan/Libation/releases/latest) and run it on any Windows, Mac, or Linux machine. When prompted to choose an interface, pick **Chardonnay** (the modern cross-platform UI). Do not install to `Program Files` on Windows — extract the zip to a user-owned folder instead.

### Step 2 — Add Your Audible Account

1. Open Libation and go to **Accounts → Manage Accounts**.
2. Click **Add Account** and select your Audible locale (e.g., *Amazon US*).
3. Enter your Amazon/Audible credentials. Audible may require a CAPTCHA or two-factor challenge — the desktop app handles this interactively. If login loops or fails, try the **"Log in with browser"** option which opens an external browser flow instead of the built-in form.
4. Once authenticated, Libation will perform an initial library scan and populate your full book list.

### Step 3 — Configure Download Settings

Before copying the config, set up your download preferences in the desktop app so `Settings.json` captures them. In **Settings → Download/Decrypt**:

- **Books folder** — set this to anything; the Docker container ignores this value and uses `LIBATION_BOOKS_DIR` (`/data`) instead.
- **File naming template** — customize how downloaded files are named. A useful pattern:
  ```
  <if series-><series> - <-if series><title>
  ```
  This puts series-based books in a subfolder like `The Stormlight Archive - The Way of Kings`.
- **Output format** — choose between keeping the original M4B (default, lossless) or converting to MP3. MP3 conversion is lossy and slower but maximizes compatibility. M4B plays natively on Apple devices and most modern players.

### Step 4 — Copy Config Files to the Host

Locate the Libation settings directory on the machine where you ran the desktop app:

| OS | Path |
|---|---|
| Windows | `%APPDATA%\Libation\` |
| macOS | `~/Library/Application Support/Libation/` |
| Linux | `~/.config/Libation/` |

Copy **both** files to the Docker config volume on TrueNAS:

```bash
# From your local machine (adjust source path for your OS)
scp "%APPDATA%\Libation\AccountsSettings.json" truenas:/mnt/SSD/Containers/libation/config/
scp "%APPDATA%\Libation\Settings.json"         truenas:/mnt/SSD/Containers/libation/config/
```

Then fix ownership on the host:

```bash
chown -R 3001:3001 /mnt/SSD/Containers/libation/config
```

### Step 5 — Start the Container

```bash
cp example.env .env   # defaults are fine; adjust SLEEP_TIME if desired
docker compose up -d
docker compose logs -f
```

A successful first scan looks like:

```
Scanning library for new books...
Found 142 books in library
Downloading: The Way of Kings (Part 1)...
Download complete: /data/Stormlight Archive/The Way of Kings.m4b
```

---

## Ongoing Use

Once running, Libation is fully autonomous. Every `SLEEP_TIME` interval it:

1. Scans your Audible library for new purchases or pre-orders that have become available.
2. Downloads and decrypts any titles not already present in `/data`.
3. Writes the final M4B (or MP3) file and a `.cue` chapter file to the output directory.

Audiobookshelf will pick up new files automatically if its library scan is configured (or triggered manually).

### Checking Download Status

```bash
# Live logs
docker compose logs -f libation

# See what's been downloaded
ls /mnt/Data/Media/Audiobooks/
```

### Re-authenticating After a Token Expiry

Audible tokens do eventually expire. If you see authentication errors in the logs:

1. Open the desktop app on any machine and log in again.
2. Re-copy `AccountsSettings.json` to `/mnt/SSD/Containers/libation/config/`.
3. Restart the container: `docker compose restart libation`

### Triggering a Manual Scan

If you just bought a book and don't want to wait for the next scheduled scan:

```bash
docker compose restart libation
```

The container scans immediately on startup, then resumes its normal `SLEEP_TIME` loop.

---

## Output Files

Downloaded books land in `/mnt/Data/Media/Audiobooks/` with the naming structure defined in `Settings.json`. Each title produces:

| File | Description |
|---|---|
| `<title>.m4b` | The audiobook audio (AAC, lossless from Audible) |
| `<title>.cue` | Chapter markers for players that support cue sheets |

M4B files are natively playable on Apple devices, VLC, and most modern media players. Audiobookshelf reads both the audio and chapter data.

---

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

- **No Traefik / no ports** — this service has no web UI and is not in the port registry.
- **User mapping** — Libation's image defaults to UID 1001. This compose file overrides it with `user: "${PUID}:${PGID}"` to match the rest of the homelab (3001:3001). If you see permission errors, confirm host directory ownership matches.
- **Books/InProgress paths in Settings.json are ignored** — the container always uses the `LIBATION_BOOKS_DIR` env var (`/data`). Don't waste time trying to set the path inside the app.
- **SLEEP_TIME=-1** — use this if you prefer to drive scans from an external cron job rather than the container's internal loop.
- **PostgreSQL** — the `LIBATION_CONNECTION_STRING` env var (not set here) lets you swap SQLite for PostgreSQL if you need remote access to the metadata.
