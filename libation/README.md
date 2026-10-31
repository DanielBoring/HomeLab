# Libation

[Libation](https://getlibation.com) is a headless Audible audiobook manager that periodically scans your Audible library and downloads your purchases as DRM-free audio files (M4B/MP3). It runs as a background daemon with no web UI — once configured it silently keeps your local library in sync.

The typical use case in this homelab is to feed downloaded books directly into the Audiobookshelf library at `/mnt/Data/Media/Audiobooks`.

## Architecture

```text
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

Desktop setup and private config transfer are the approach below. Current
upstream also documents CLI `login-external`/`import-account`; availability must
match the selected image version, which is not inventoried here. Do not treat
desktop setup as the only upstream-supported method.

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
  ```text
  <if series-><series> - <-if series><title>
  ```
  This puts series-based books in a subfolder like `The Stormlight Archive - The Way of Kings`.
- **Output format** — choose between keeping the original M4B (default, lossless) or converting to MP3. MP3 conversion is lossy and slower but maximizes compatibility. M4B plays natively on Apple devices and most modern players.

### Step 4 — Copy Config Files to the Host

Find the actual **Libation files/settings directory** selected in your desktop
installation; do not assume `%APPDATA%` or a fixed OS path. Upstream usually
uses a Libation directory under the user's home.

For encrypted tokens, export the desktop encryption key using **Settings →
Important → Export encryption key**, and transfer `libation-master.key` alongside
the account/settings files. The desktop OS secret store is not available inside
Docker. Treat all three files as credentials and transfer only over a trusted,
encrypted connection.

Example from Windows/PowerShell, replacing the source directory and SSH host:

```powershell
$LibationFiles = 'C:\path\to\your\Libation-files'
scp "$LibationFiles\AccountsSettings.json" "$LibationFiles\Settings.json" truenas:/mnt/SSD/Containers/libation/config/
# When tokens are encrypted, also transfer the exported key:
scp "$LibationFiles\libation-master.key" truenas:/mnt/SSD/Containers/libation/config/
```

Then fix ownership on the host:

```bash
chown 3001:3001 /mnt/SSD/Containers/libation/config/AccountsSettings.json \
  /mnt/SSD/Containers/libation/config/Settings.json
# If transferred, protect the matching key the same way:
chmod 600 /mnt/SSD/Containers/libation/config/AccountsSettings.json
if [ -f /mnt/SSD/Containers/libation/config/libation-master.key ]; then
  chown 3001:3001 /mnt/SSD/Containers/libation/config/libation-master.key &&
    chmod 600 /mnt/SSD/Containers/libation/config/libation-master.key
fi
```

### Step 5 — Start the Container

```bash
cp .env.example .env   # defaults are fine; adjust SLEEP_TIME if desired
docker compose up -d
docker compose logs -f
```

A successful first scan looks like:

```text
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
2. Pause scans, preserve the old config, and transfer updated
   `AccountsSettings.json` **and its matching exported key** if encrypted.
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
| `/config` | `/mnt/SSD/Containers/libation/config` | Accounts/settings and matching exported `libation-master.key` if tokens are encrypted |
| `/db` | `/mnt/SSD/Containers/libation/db` | Libation SQLite database |
| `/data` | `/mnt/Data/Media/Audiobooks` | Downloaded audiobook files |

## Notes

- **No Traefik / no ports** — this service has no web UI and is not in the port registry.
- **User mapping** — Libation's image defaults to UID 1001. This compose file overrides it with `user: "${PUID}:${PGID}"` to match the rest of the homelab (3001:3001). If you see permission errors, confirm host directory ownership matches.
- **Books/InProgress paths in Settings.json are ignored** — the container always uses the `LIBATION_BOOKS_DIR` env var (`/data`). Don't waste time trying to set the path inside the app.
- **SLEEP_TIME=-1** — use this if you prefer to drive scans from an external cron job rather than the container's internal loop.
- **PostgreSQL** — the `LIBATION_CONNECTION_STRING` env var (not set here) lets you swap SQLite for PostgreSQL if you need remote access to the metadata.

## Operations and recovery

Linux host preparation/Compose commands run from `libation/`; Windows transfer
examples are labelled separately. Ownership setup is for fresh directories,
not blanket permission changes to an existing media library. Allow UID/GID
3001 access through the existing media ACLs.

Stop scans before backing up `config`, `db`, and irreplaceable audiobooks
together with original image/settings. Keep the account token/key files private.
Use the [shared isolated restore procedure](../README.md#backing-up-data), verify
metadata and token decryption without starting a bulk download, and then resume
scheduled scans. Review matching-version migrations before changing the
unresolved moving image.

Encrypted-token transfer guidance was checked against
[upstream Docker documentation](https://github.com/rmcrackan/Libation/blob/master/docs/installation/docker.md)
on 2026-10-13; the installed version and account login were not live-tested.
