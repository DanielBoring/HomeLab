# PegaProx

A web-based management interface for Proxmox VE clusters. It gives you a single dashboard to manage multiple hypervisors — live VM monitoring, start/stop/snapshot controls, noVNC console access, and an SSH terminal — all from a browser.

**Why run it:** Proxmox's built-in UI is per-node. PegaProx aggregates multiple nodes/clusters into one view and adds a cleaner UX for day-to-day operations.

**When it makes sense:** If you have a Proxmox cluster (even a single node) and want a lightweight management UI that's accessible via a standard HTTPS domain on your LAN.

## Architecture

```
Browser
  │
  ├── HTTPS :443 → Traefik → PegaProx :5000  (web UI + API)
  ├── WS :5001 → direct → PegaProx :5001      (noVNC console)
  └── WS :5002 → direct → PegaProx :5002      (SSH terminal)
```

The main UI and REST API go through Traefik (LAN-only, HTTPS). The VNC and SSH websocket ports are exposed directly on the host — browsers open those connections independently, and routing them through Traefik as separate routers adds complexity without benefit on a LAN.

**Default credentials:** `pegaprox` / `admin` — change immediately after first login.

## Prerequisites

Create the host directories before starting:

```bash
mkdir -p /mnt/SSD/Containers/pegaprox/config
mkdir -p /mnt/SSD/Containers/pegaprox/logs
```

## Quick Start

```bash
cp example.env .env
# Edit .env with your domain
docker compose up -d
```

Navigate to `https://<PEGAPROX_DOMAIN>` and log in with the default credentials.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TZ` | `America/New_York` | Timezone |
| `PEGAPROX_DOMAIN` | — | **Required.** Traefik domain for the web UI |
| `PEGAPROX_VNC_PORT` | `5001` | Host port for noVNC websocket |
| `PEGAPROX_SSH_PORT` | `5002` | Host port for SSH websocket |

## Ports

| Port | Protocol | Purpose |
|---|---|---|
| `443` (via Traefik) | HTTPS | Web UI + API |
| `5001` (host direct) | WS | noVNC console websocket |
| `5002` (host direct) | WS | SSH terminal websocket |

## Volumes

| Path | Purpose |
|---|---|
| `/mnt/SSD/Containers/pegaprox/config` | Configuration database |
| `/mnt/SSD/Containers/pegaprox/logs` | Application logs |
