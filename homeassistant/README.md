# Home Assistant

Open-source home automation platform that puts local control and privacy first. Connects to thousands of devices and services — lights, sensors, locks, cameras, media players, thermostats — and lets you build automations, dashboards, and alerts without any data leaving your network.

## Why run it

Most smart home ecosystems require a cloud account and send your usage data to a vendor. Home Assistant runs entirely on your network. Automations fire locally even if the internet is down, and no vendor can sunset their app and brick your devices. It also unifies fragmented ecosystems — Zigbee, Z-Wave, Matter, HomeKit, Google Home, Alexa, and hundreds more can all be controlled from a single interface.

## Overview

| Setting | Value |
|---|---|
| Image | `lscr.io/linuxserver/homeassistant:latest` |
| HTTPS access | `https://<HOMEASSISTANT_DOMAIN>` (via Traefik) |
| Direct access | `http://<host-ip>:8123` (companion app, local tablets) |
| Config | `/mnt/SSD/Containers/homeassistant` |

## Architecture

```
Companion app / browser
        │
        ▼
  Traefik (HTTPS 443)                    Direct LAN
  <HOMEASSISTANT_DOMAIN>    ──OR──    host-ip:8123
        │                                   │
        └──────────────────┬────────────────┘
                           ▼
              homeassistant container (:8123)
                           │
                    /config (bind mount)
              /mnt/SSD/Containers/homeassistant
```

Traefik terminates TLS and forwards HTTP to the container on the `traefik` Docker network. The direct port binding (`8123`) stays open for the HA Companion app and any local clients (wall tablets, embedded dashboards) that bypass Traefik.

## Prerequisites

### 1. Create the storage directory

```bash
mkdir -p /mnt/SSD/Containers/homeassistant
chown -R 3001:3001 /mnt/SSD/Containers/homeassistant
```

### 2. Ensure the traefik network exists

```bash
docker network ls | grep traefik
```

If it doesn't exist, deploy the Traefik stack first.

## Quick Start

### 1. Copy the environment template

```bash
cp .env.example .env
```

### 2. Edit `.env`

| Variable | Required | Description |
|---|---|---|
| `HOMEASSISTANT_DOMAIN` | Yes | Hostname Traefik routes to HA (e.g. `ha.yourdomain.com`) |
| `TZ` | No | Timezone — defaults to `America/New_York` |
| `HOMEASSISTANT_PORT` | No | Host port for direct LAN access — defaults to `8123` |

### 3. Deploy

```bash
docker compose up -d
```

### 4. Add a DNS record

Point your subdomain at the Traefik macvlan IP:

```
<HOMEASSISTANT_DOMAIN>  A  10.0.5.5
```

### 5. Configure trusted proxies (required for Traefik)

After the container starts, edit `/mnt/SSD/Containers/homeassistant/configuration.yaml` and add:

```yaml
homeassistant:
  use_x_forwarded_for: true
  trusted_proxies:
    - 172.16.0.0/12   # Docker bridge networks
    - 10.0.0.0/8      # LAN + Traefik macvlan
```

Then restart the container:

```bash
docker compose restart homeassistant
```

Without this, HA will see the Traefik container IP as every client's address. This causes false IP ban triggers and breaks Lovelace WebSocket connections.

### 6. Access

```
https://<HOMEASSISTANT_DOMAIN>
```

Create your owner account on first launch. HA walks you through initial setup automatically.

## Storage

| Data | Path |
|---|---|
| Configuration, automations, scripts | `/mnt/SSD/Containers/homeassistant` |

All HA config lives in a single directory — easy to back up and restore.

## Device Passthrough (Zigbee / Z-Wave)

If you have a USB Zigbee or Z-Wave dongle, pass it through to the container. First find the stable device path using udev rules (paths like `/dev/ttyUSB0` can shift after reboot):

```bash
ls /dev/serial/by-id/
```

Then uncomment and update the `devices` block in `compose.yaml`:

```yaml
devices:
  - /dev/serial/by-id/usb-Silicon_Labs_HubZ_Smart_Home_Controller_XXXXXXXX-if00-port0:/dev/ttyUSB0
```

### Network mode note

This compose file uses the `traefik` Docker network (bridge mode) for Traefik integration. Bridge mode works for all USB-based integrations. However, **if you need mDNS, Bluetooth, or broadcast-based device discovery** (e.g. Matter, Thread, some smart TV integrations), you will need `network_mode: host` instead.

With `network_mode: host`, Traefik labels stop working — remove them and access HA on the direct port only. The `trusted_proxies` block in `configuration.yaml` also becomes unnecessary.

## Maintenance

### Update

```bash
docker compose pull
docker compose up -d
```

Pin to a specific release tag in `compose.yaml` to prevent surprise breaking changes:

```yaml
image: lscr.io/linuxserver/homeassistant:2025.4.4
```

HA releases monthly (e.g. `2025.4.x`). Review the [release notes](https://www.home-assistant.io/blog/categories/release-notes/) before updating — integrations occasionally have breaking changes.

### Backup

```bash
docker compose down
tar -czf homeassistant-backup-$(date +%Y%m%d).tar.gz /mnt/SSD/Containers/homeassistant
docker compose up -d
```

HA also has a built-in backup tool under **Settings → System → Backups** that can be automated via an automation.
