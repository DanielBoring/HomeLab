# Uptime Kuma

Self-hosted uptime monitoring with a clean web UI. Monitors services via HTTP/HTTPS, TCP, DNS, and more, with alerting via a wide range of notification providers.

## Overview

| Setting | Value |
|---|---|
| Image | `louislam/uptime-kuma:latest` |
| Access | `https://uptime-kuma.virtuallyboring.com` (via Traefik) |
| Config | `/mnt/SSD/Containers/uptime-kuma` |

## Prerequisites

Create the persistent storage directory before deploying:

```bash
mkdir -p /mnt/SSD/Containers/uptime-kuma
```

> Uptime Kuma runs as root internally — no `chown` required.

## Quick Start

### 1. Copy the environment template

```bash
cp .env.example .env
```

### 2. Edit the .env file

```bash
nano .env
```

| Variable | Description |
|---|---|
| `UPTIME_KUMA_DOMAIN` | Hostname Traefik routes to Uptime Kuma (e.g. `uptime-kuma.virtuallyboring.com`) |

### 3. Deploy

```bash
docker compose up -d
```

### 4. Add DNS record

In your Windows DNS server, add a CNAME pointing to the Traefik A record:

```
uptime-kuma.virtuallyboring.com  CNAME  traefik.virtuallyboring.com
```

### 5. Access

```
https://uptime-kuma.virtuallyboring.com
```

Create an admin account on first launch.

## Storage

| Data | Path |
|---|---|
| Database, config | `/mnt/SSD/Containers/uptime-kuma` |

## Maintenance

### Update image

```bash
docker compose pull
docker compose up -d
```

### Backup

```bash
docker compose down
tar -czf uptime-kuma-backup-$(date +%Y%m%d).tar.gz /mnt/SSD/Containers/uptime-kuma
docker compose up -d
```
