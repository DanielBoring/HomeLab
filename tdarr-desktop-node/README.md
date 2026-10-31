# Tdarr Desktop Node

This is a Tdarr worker node that runs on the gaming desktop (NVIDIA RTX 3090). It connects to the Tdarr server running on TrueNAS over the LAN and processes transcode jobs using the 3090's GPU.

Tdarr's node model is designed for exactly this use case: nodes can come and go without losing queue state. When the desktop is on, it pulls jobs and crunches through them; when it's off, TrueNAS's own node carries on. The 3090 is significantly faster than the TrueNAS GPU for encoding, so leaving this running while gaming-idle will make a large dent in a backlog.

## Architecture

```text
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
- Supported NVIDIA Windows driver and Docker Desktop WSL2 GPU support; do not
  install a Linux NVIDIA toolkit onto Windows using generic Linux commands.
- The Docker Linux backend must be able to mount the TrueNAS NFSv4 export.
  Enabling the Windows NFS client is not required by Docker's Linux volume driver.
- Local directories created:
  ```powershell
  New-Item -ItemType Directory -Force -Path C:\Docker\tdarr\configs,C:\Docker\tdarr\logs,C:\Docker\tdarr\transcode-cache
  ```

## Quick Start

Run from this directory on Windows/PowerShell:

```powershell
Copy-Item .env.example .env
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

Worker limits are fixed in Compose: two GPU and two CPU transcode workers, and
one of each healthcheck worker. Change the reviewed service environment in
`compose.yaml`, not `.env`, and recreate the node to apply it. Workload suitability
depends on codecs, GPU memory and gaming load; tune conservatively.

## Mounts and recovery

Config, logs and scratch paths use **direct binds** so Docker Desktop translates
Windows paths. This is an intentional exception to the Linux host's named
bind-volume convention; the old local driver's Linux `mount` options cannot
translate `C:\...` paths. Existing old named-volume metadata is not deleted.
Confirm Docker Desktop can share the three pre-created paths before recreation.

Media remains a read/write Linux NFSv4 named volume. Limit the export to the
worker and verify UID/GID/ACL access; this node can replace original media.
Keep a separately verified media backup and test plugins on copies first.
Static Compose validation does not prove Docker Desktop NFS/GPU compatibility.
If the backend cannot mount NFS, do not silently switch to different media
paths: stop and design a supported mount/path-translation approach.

Back up node config and irreplaceable media; scratch/logs are optional. The
server holds queue/library state. Follow the
[shared recovery safeguards](../README.md#backing-up-data), restore original
image/settings and config, then verify registration and a disposable test job.
This stack's image still needs an approved version selection/running-image
inventory; do not upgrade it independently of the server without compatibility
review.
