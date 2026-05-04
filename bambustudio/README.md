# Bambu Studio

Bambu Studio is the official slicing software for Bambu Lab 3D printers, providing a full GUI accessible from any browser via KasmVNC. Running it as a container lets you slice models from any device on your network without installing the desktop app locally — useful when your printer host or NAS is always-on but your workstation isn't.

**When to use this over the desktop app:** If you want a single always-available slicing environment with your profiles and filament libraries in one place, or if you need to slice from a tablet, thin client, or any machine without a local install.

[https://docs.linuxserver.io/images/docker-bambustudio/]

## Architecture

```
Browser (HTTPS) → Traefik (TLS termination) → bambustudio:3000 (KasmVNC HTTP)
```

The container runs Bambu Studio inside a KasmVNC session and streams it to the browser over HTTP on port 3000. Traefik handles TLS, so the browser still gets a valid HTTPS connection. The built-in `CUSTOM_USER`/`PASSWORD` basic auth adds a second layer of authentication on top of the `lan-only` Traefik middleware.

> **Note:** This image is x86-64 only. It will not run on ARM hosts.

## Prerequisites

- Traefik running and the `traefik` external network created
- Host storage directory created on TrueNAS:
  ```sh
  mkdir -p /mnt/SSD/Containers/bambustudio
  ```
- DNS record for `bambustudio.yourdomain.com` pointing to Traefik's IP (`10.0.5.5`)

## Quick Start

```sh
cp example.env .env
# Fill in BAMBUSTUDIO_USER and BAMBUSTUDIO_PASSWORD
docker compose up -d
```

Navigate to `https://bambustudio.yourdomain.com` and log in with your configured credentials.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TZ` | `America/New_York` | Container timezone |
| `PUID` | `3001` | User ID for file permissions |
| `PGID` | `3001` | Group ID for file permissions |
| `BAMBUSTUDIO_DOMAIN` | — | Full domain for Traefik routing |
| `BAMBUSTUDIO_USER` | — | KasmVNC basic auth username |
| `BAMBUSTUDIO_PASSWORD` | — | KasmVNC basic auth password |
| `DARK_MODE` | `true` | Enable dark mode in the web UI |

### Optional variables (add to `.env` as needed)

| Variable | Description |
|---|---|
| `DRINODE` | GPU device path for hardware rendering (e.g. `/dev/dri/renderD128`) |
| `AUTO_GPU` | Set to `true` to auto-detect an Intel/AMD/Nvidia GPU |
| `LC_ALL` | Locale override (e.g. `en_US.UTF-8`) |

## GPU Acceleration

To enable GPU-accelerated rendering, add the device to `compose.yaml` under the `bambustudio` service and set `DRINODE`:

```yaml
devices:
  - /dev/dri/renderD128:/dev/dri/renderD128
environment:
  - DRINODE=/dev/dri/renderD128
```
