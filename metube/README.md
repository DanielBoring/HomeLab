# MeTube

Web GUI for [yt-dlp](https://github.com/yt-dlp/yt-dlp) — paste a URL, pick a format, and download video or audio from YouTube and hundreds of other sites. Supports playlists, subscriptions, and custom yt-dlp options.

## Why run it

yt-dlp from the command line works, but MeTube gives you a persistent queue, format selection (video/audio/best), and a browser-accessible download history without touching a terminal. Useful for pulling content to your local media library or archiving videos before they disappear.

## Architecture

```
Browser → Traefik (HTTPS, lan-only) → MeTube :8081
                                          │
                          /downloads → /mnt/Data/Media/Downloads/Untube  (HDD)
                          /config    → /mnt/SSD/Containers/metube         (SSD — queue state)
```

Downloads land directly in your media storage. The queue state (what's been downloaded, subscriptions) stays on the SSD so it survives container restarts and is fast to read.

## Prerequisites

- Traefik running with the `traefik` external network
- Host directories created before first start:

```bash
mkdir -p /mnt/Data/Media/Downloads/Untube
mkdir -p /mnt/SSD/Containers/metube
chown -R 3001:3001 /mnt/Data/Media/Downloads/Untube /mnt/SSD/Containers/metube
```

## Quick start

```bash
cp example.env .env
# Edit .env — set METUBE_DOMAIN at minimum
docker compose up -d
```

Open `https://<METUBE_DOMAIN>` in a browser.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `TZ` | `America/New_York` | Timezone |
| `PUID` | `3001` | UID to run as |
| `PGID` | `3001` | GID to run as |
| `UMASK` | `002` | File creation mask — group-writable so arr services can read downloads |
| `METUBE_DOMAIN` | — | FQDN exposed via Traefik, e.g. `metube.virtuallyboring.com` |
| `METUBE_PORT` | `8091` | Host port (direct access fallback) |
| `METUBE_MAX_CONCURRENT` | `3` | Max simultaneous downloads |

### Optional yt-dlp tuning (uncomment in compose.yaml)

| Variable | Example | Description |
|---|---|---|
| `YTDL_OPTIONS` | `{"writesubtitles": true}` | JSON object passed directly to yt-dlp |
| `OUTPUT_TEMPLATE` | `%(title)s.%(ext)s` | yt-dlp filename template |

Full list of yt-dlp options: <https://github.com/yt-dlp/yt-dlp#usage-and-options>

## Notes

- The UI is restricted to LAN (`10.0.0.0/20`) via `lan-only@file` middleware — MeTube has no built-in auth.
- `UMASK=002` matches the arr stack convention so downloaded files are group-writable.
- Audio-only downloads go to the same folder as video; set `AUDIO_DOWNLOAD_DIR` in compose.yaml if you want a separate path.
- Subscriptions and queue history live in `/mnt/SSD/Containers/metube/` — back this up if you use subscriptions heavily.
