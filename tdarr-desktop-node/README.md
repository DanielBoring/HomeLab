# Tdarr Desktop Node

This is a Tdarr worker node that runs on the gaming desktop (NVIDIA RTX 3090). It connects to the Tdarr server running on TrueNAS over the LAN and processes transcode jobs using the 3090's GPU.

Tdarr's node model is designed for exactly this use case: nodes can come and go without losing queue state. When the desktop is on, it pulls jobs and crunches through them; when it's off, TrueNAS's own node carries on. The 3090 is significantly faster than the TrueNAS GPU for encoding, so leaving this running while gaming-idle will make a large dent in a backlog.

## Architecture

```
Gaming Desktop                          TrueNAS (LAN)
┌──────────────────────┐               ┌──────────────────┐
│ tdarr-node-desktop   │──── :8266 ───►│ tdarr server     │
│ RTX 3090             │               │                  │
│                      │               │ /mnt/Data/Media  │
│ NFS mount ◄──────────┼───────────────┘                  │
│  /data/media         │  (reads/writes media over LAN)   │
└──────────────────────┘
```

Media files are accessed via NFS mount from TrueNAS. Transcode scratch space is a local path on the desktop — keeps temp files off the network.

## Prerequisites

**TrueNAS:**
- NFS export configured for `/mnt/Data/Media` — allow the desktop's LAN IP

**Gaming desktop:**
- Docker Desktop with WSL2 backend
- NVIDIA Container Toolkit: [docs.nvidia.com/datacenter/cloud-native/container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
- NFS client enabled in Windows (optional features → Services for NFS → Client for NFS)
- Local directories created:
  ```
  mkdir C:\Docker\tdarr\configs
  mkdir C:\Docker\tdarr\logs
  mkdir C:\Docker\tdarr\transcode-cache
  ```

## Quick Start

```bash
cp example.env .env
# Edit .env — set TDARR_SERVER_IP and TRUENAS_IP to the TrueNAS LAN IP
docker compose up -d
```

Open the Tdarr web UI → **Nodes** — `Desktop-3090` should appear within ~30 seconds.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TZ` | `America/New_York` | Container timezone |
| `PUID` | `1000` | User ID (Docker Desktop default) |
| `PGID` | `1000` | Group ID (Docker Desktop default) |
| `TDARR_SERVER_IP` | — | TrueNAS LAN IP address |
| `TRUENAS_IP` | — | TrueNAS IP for NFS mount (usually same as above) |
| `TDARR_CONFIGS_PATH` | `C:\Docker\tdarr\configs` | Local path for node config |
| `TDARR_LOGS_PATH` | `C:\Docker\tdarr\logs` | Local path for logs |
| `TDARR_TRANSCODE_PATH` | `C:\Docker\tdarr\transcode-cache` | Local scratch space for in-progress encodes |

## Worker Limits

The compose sets `transcodegpuWorkers=2` and `transcodecpuWorkers=2`. The 3090 has enough VRAM and compute to run two concurrent GPU encodes. Raise or lower in `.env` → restart to apply.
