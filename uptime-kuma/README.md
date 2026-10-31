# Uptime Kuma

Self-hosted uptime monitoring with a clean web UI. Monitors services via HTTP/HTTPS, TCP, DNS, and more, with alerting via a wide range of notification providers.

Images in `compose.yaml` are frozen to the inventoried builds. See the [image update guide](../README.md#image-updates); `docker compose pull` alone does not upgrade them.

## Overview

| Setting | Value |
|---|---|
| Image | `louislam/uptime-kuma`, digest-pinned in [compose.yaml](compose.yaml) |
| Access | `https://<UPTIME_KUMA_DOMAIN>` (via Traefik) |
| Config | `/mnt/SSD/Containers/uptime-kuma` |

## Prerequisites

Deploy Traefik first; run Linux/Bash commands from `uptime-kuma/`.
The Docker socket mount permits privileged daemon access even with `:ro`;
restrict administration to trusted users.

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
| `UPTIME_KUMA_DOMAIN` | Hostname Traefik routes to Uptime Kuma (e.g. `uptime-kuma.yourdomain.com`) |

### 3. Deploy

```bash
docker compose up -d
```

### 4. Add DNS record

In your Windows DNS server, add a CNAME pointing to the Traefik A record:

```text
<UPTIME_KUMA_DOMAIN>  CNAME  traefik.yourdomain.com
```

### 5. Access

```text
https://<UPTIME_KUMA_DOMAIN>
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

Stop the container before preserving the entire data path, image pins and
encrypted settings. Use the [shared recovery procedure](../README.md#backing-up-data).
Restore with original ownership/version, verify users, monitors and history, and
keep notification delivery disabled until the restore is accepted. A healthy
container does not prove each configured monitor is functioning.
