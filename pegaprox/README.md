# PegaProx

A web-based management interface for Proxmox VE clusters. It gives you a single dashboard to manage multiple hypervisors — live VM monitoring, start/stop/snapshot controls, noVNC console access, and an SSH terminal — all from a browser.

**Why run it:** Proxmox's built-in UI is per-node. PegaProx aggregates multiple nodes/clusters into one view and adds a cleaner UX for day-to-day operations.

**When it makes sense:** If you have a Proxmox cluster (even a single node) and want a lightweight management UI that's accessible via a standard HTTPS domain on your LAN.

Images in `compose.yaml` are frozen to the inventoried builds. See the [image update guide](../README.md#image-updates); `docker compose pull` alone does not upgrade them.

## Architecture

```text
Browser
  │
  └── HTTPS :443 → Traefik → PegaProx :5000  (web UI, API, and all WebSocket traffic)
                                    │
                              internal IPC only
                                    │
                              localhost:5001  (noVNC subprocess)
                              localhost:5002  (SSH subprocess)
```

All browser traffic — including the noVNC console and SSH terminal WebSockets — flows through port 5000 via Traefik. Ports 5001 and 5002 are **internal IPC** between PegaProx's main process and its websocket subprocesses; they are never browser-facing and should not be exposed on the host.

### Proxy note

The upstream docs mention a `PEGAPROX_BEHIND_PROXY` env var — do not set it. When enabled, PegaProx switches its internal subprocess connections from `ws://localhost:5001` to `wss://localhost:5001`, but the subprocess servers don't speak TLS. This causes a flood of `Invalid HTTP method` TLS handshake errors in the logs and breaks the console and terminal entirely.

**Default credentials:** `pegaprox` / `admin` — change immediately after first login.

## Prerequisites

Deploy Traefik first; run Linux/Bash examples from `pegaprox/`.

Create the host directories before starting:

```bash
mkdir -p /mnt/SSD/Containers/pegaprox/config
mkdir -p /mnt/SSD/Containers/pegaprox/logs
```

## Quick Start

```bash
cp .env.example .env
# Edit .env with your domain
docker compose up -d
```

Navigate to `https://<PEGAPROX_DOMAIN>` and log in with the default credentials.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TZ` | `America/New_York` | Timezone |
| `PEGAPROX_DOMAIN` | — | **Required.** Traefik domain for the web UI |

## Ports

| Port | Purpose |
|---|---|
| `443` via Traefik | Web UI, API, noVNC console, SSH terminal |

## Volumes

| Path | Purpose |
|---|---|
| `/mnt/SSD/Containers/pegaprox/config` | Configuration database |
| `/mnt/SSD/Containers/pegaprox/logs` | Application logs |

## Operations and recovery

This interface can alter VMs and open host terminals. Protect accounts, stored
credentials and allowed source networks; a dashboard is not read-only.
Check `docker compose ps`, recent `pegaprox` logs and a harmless cluster inventory
view, not a VM power operation.

Stop the app before preserving both paths, original images and encrypted private
settings using the [shared recovery procedure](../README.md#backing-up-data).
Restore privately at the same version/ownership, verify login and saved clusters,
then reconnect with least-privilege credentials. These are app-state backups,
not Proxmox VM backups. Review upstream migrations before changing the digest.
