# Unmanic

Unmanic is an automated media library optimiser. It scans a directory for media files, runs them through a plugin pipeline (remux, re-encode, subtitle extraction, etc.), and replaces the originals in-place. The key idea is a rule-based worker queue: you define what "good" looks like (codec, container, audio tracks, resolution) and Unmanic continuously finds files that don't match and fixes them.

**Why run it:** Unlike Tdarr — which uses a node-based distributed transcoding model — Unmanic is a simpler single-node tool with a plugin-first architecture. It's well suited for set-and-forget library clean-up tasks like converting everything to H.265/HEVC or stripping unwanted audio tracks.

**When it makes sense:**
- You want to optimise an existing library without manually managing a transcoding queue
- You need fine-grained plugin control over per-file decisions (e.g. skip files already in HEVC, only process files over 10 GB)
- You prefer a lighter-weight alternative to Tdarr for a single-host setup

## Architecture

```
Browser → Traefik (TLS) → Unmanic :8888
                                  ├── /config  → /mnt/SSD/Containers/unmanic/config
                                  ├── /library → /mnt/Data/Media   (scanned + processed in-place)
                                  └── /tmp/unmanic → /mnt/SSD/Containers/unmanic/cache
```

Unmanic runs a single worker process (configurable) that picks tasks off the queue, processes them through the plugin pipeline into the cache directory, then atomically replaces the source file on success.

## Prerequisites

Create the host directories before starting:

```bash
mkdir -p /mnt/SSD/Containers/unmanic/config
mkdir -p /mnt/SSD/Containers/unmanic/cache
```

`/mnt/Data/Media` must already exist — it is the shared media volume used by the arr stack.

### Optional: Intel Arc A310 hardware acceleration (VAAPI)

Unmanic supports VAAPI for hardware-accelerated encoding. To enable it, uncomment the `devices` block in `compose.yaml`:

```yaml
devices:
  - /dev/dri:/dev/dri
```

Then install the VAAPI plugin in the Unmanic UI and set the encoder to `hevc_vaapi` (or `h264_vaapi`). Verify the device node is available on the host with `ls /dev/dri`.

## Quick Start

1. `cp example.env .env` and set `UNMANIC_DOMAIN`
2. Create host directories (see Prerequisites)
3. `docker compose up -d`
4. Open `https://<UNMANIC_DOMAIN>` — complete the setup wizard
5. Add a library pointing to `/library` and enable your chosen plugins

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TZ` | `America/New_York` | Timezone |
| `PUID` | `3001` | User ID for file ownership |
| `PGID` | `3001` | Group ID for file ownership |
| `UNMANIC_DOMAIN` | — | Traefik hostname (required) |
| `UNMANIC_PORT` | `8888` | Host port (optional override) |
