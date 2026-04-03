# Uptime Kuma

Self-hosted uptime monitoring with a clean web UI. Monitors services via HTTP/HTTPS, TCP, DNS, and more, with alerting via a wide range of notification providers.

## Services

| Service | Port | Description |
|---|---|---|
| Uptime Kuma | 3002 | Uptime monitoring web UI |

## Prerequisites

Create the persistent storage directory before deploying:

```bash
mkdir -p /mnt/SSD/Containers/uptime-kuma
```

> Uptime Kuma runs as root internally — no `chown` required.

## Quick Start

### 1. Deploy

```bash
docker compose up -d
```

### 2. Verify

```bash
docker compose ps
docker compose logs -f uptime-kuma
```

### 3. Initial Setup

Navigate to `http://<host-ip>:3002` and create an admin account on first launch.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `UPTIME_KUMA_PORT` | `3002` | Host port for the web UI |

To override, create a `.env` file:

```bash
UPTIME_KUMA_PORT=3002
```

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
