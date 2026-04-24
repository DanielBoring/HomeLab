# Tdarr

Tdarr is a distributed media transcoding automation platform. It scans a media library, applies codec conversion rules (H.265, AV1, etc.), and manages a queue of transcode jobs across one or more worker nodes. The result is a smaller library with files in modern codecs — meaning less storage consumed and more Direct Play for Plex clients instead of on-the-fly transcoding.

**Run it when:**
- Your library has a lot of H.264 content that could shrink 40–60% by converting to H.265/HEVC
- You want Plex to Direct Play more often (fewer transcodes = less CPU/GPU load at watch time)
- You have idle GPU cycles that could be doing useful work overnight

## Architecture

```
┌─────────────────────────────────────────────────┐
│ TrueNAS Docker Host                             │
│                                                  │
│  ┌──────────────┐    ┌──────────────────────┐   │
│  │ tdarr        │    │ tdarr-node           │   │
│  │ (server)     │◄───│ (TrueNAS GPU worker) │   │
│  │              │    │ network_mode:        │   │
│  │ :8265 webUI  │    │   service:tdarr      │   │
│  │ :8266 comms  │    │ NVIDIA GPU           │   │
│  └──────┬───────┘    └──────────────────────┘   │
│         │                                        │
│  /mnt/Data/Media (shared volume)                │
└─────────┼───────────────────────────────────────┘
          │ Traefik
          ▼
    tdarr.yourdomain.com (LAN only)
```

The server and node run in the same compose stack. The node uses `network_mode: service:tdarr` — it shares the server container's network namespace and communicates over loopback (`serverIP=0.0.0.0`), so no extra port exposure is needed for the node.

A second node on the gaming desktop connects to port 8266 over the LAN — see [../tdarr-desktop-node/](../tdarr-desktop-node/).

**GPU contention note:** The TrueNAS GPU is also used by Plex. `transcodegpuWorkers=1` caps Tdarr to one GPU encode job at a time, leaving headroom for Plex streams. If you notice Plex transcoding degradation during heavy Tdarr runs, drop this to 0 during peak hours or use Tdarr's built-in scheduler.

## Prerequisites

**TrueNAS host:**
- NVIDIA Container Toolkit installed (`nvidia-ctk` available)
- Docker daemon configured with the NVIDIA runtime
- Host directories created before first run:
  ```
  mkdir -p /mnt/SSD/Containers/tdarr/{server,configs,logs,transcode-cache}
  ```

## Quick Start

```bash
cp example.env .env
# Edit .env — set TDARR_DOMAIN
docker compose up -d
```

Open `https://${TDARR_DOMAIN}` → **Libraries** → add a library pointing to `/data/media`.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TZ` | `America/New_York` | Container timezone |
| `PUID` | `3001` | User ID for file ownership |
| `PGID` | `3001` | Group ID for file ownership |
| `TDARR_DOMAIN` | — | Traefik domain for the web UI |
| `TDARR_PORT` | `8265` | Host port override (optional) |

## Ports

| Port | Purpose |
|---|---|
| `8265` | Web UI (exposed via Traefik) |
| `8266` | Node communication (direct, LAN only) |

## Volumes

| Host Path | Container Path | Purpose |
|---|---|---|
| `/mnt/SSD/Containers/tdarr/server` | `/app/server` | Server queue database |
| `/mnt/SSD/Containers/tdarr/configs` | `/app/configs` | Shared node configs |
| `/mnt/SSD/Containers/tdarr/logs` | `/app/logs` | Shared logs |
| `/mnt/Data/Media` | `/data/media` | Media library (read/write) |
| `/mnt/SSD/Containers/tdarr/transcode-cache` | `/temp` | Transcode scratch space |
