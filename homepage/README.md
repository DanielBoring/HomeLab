# Homepage

A modern, self-hosted dashboard for your home lab. Displays service statuses, integrates with third-party APIs, and supports Docker auto-discovery.

## Overview

| Setting | Value |
|---|---|
| Image | `ghcr.io/gethomepage/homepage:latest` |
| Access | `https://homepage.virtuallyboring.com` (via Traefik) |
| Config | `/mnt/SSD/Containers/homepage` |
| Images | `/mnt/SSD/Containers/homepage/images` |

## Prerequisites

Create the config and images directories before deploying:

```bash
mkdir -p /mnt/SSD/Containers/homepage/images
chown -R 3001:3001 /mnt/SSD/Containers/homepage
```

## Quick Start

### 1. Copy the environment template

```bash
cp .env.example .env
```

### 2. Edit the .env file

```bash
nano .env
```

The `.env` file passes API keys and URLs to Homepage via `HOMEPAGE_VAR_*` variables, which are referenced in your `services.yaml` config:

| Variable | Description |
|---|---|
| `HOMEPAGE_DOMAIN` | Hostname Traefik routes to homepage (e.g. `home.virtuallyboring.com`) |
| `HOMEPAGE_ALLOWED_HOSTS` | Must match `HOMEPAGE_DOMAIN` exactly — no port needed behind Traefik |
| `HOMEPAGE_VAR_PIHOLE1_URL` | Pi-hole 1 URL |
| `HOMEPAGE_VAR_PIHOLE1_API_KEY` | Pi-hole 1 API key |
| `HOMEPAGE_VAR_PIHOLE2_URL` | Pi-hole 2 URL |
| `HOMEPAGE_VAR_PIHOLE2_API_KEY` | Pi-hole 2 API key |
| `HOMEPAGE_VAR_PORTAINER_URL` | Portainer URL |
| `HOMEPAGE_VAR_PORTAINER_API_KEY` | Portainer API key |
| `HOMEPAGE_VAR_HOME_ASSISTANT_URL` | Home Assistant URL |
| `HOMEPAGE_VAR_HOME_ASSISTANT_API_KEY` | Home Assistant long-lived token |

### 3. Deploy

```bash
docker compose up -d
```

### 4. Add DNS records

This environment uses split-brain DNS — `virtuallyboring.com` is served by both Active Directory DNS (internal) and Cloudflare (external). Records must be added in both places depending on whether the service should be reachable internally, externally, or both.

**Internal (Active Directory DNS) — required for LAN access:**
```
traefik.virtuallyboring.com   A      10.0.5.5
homepage.virtuallyboring.com  CNAME  traefik.virtuallyboring.com
```

**External (Cloudflare) — only if you want internet access:**
```
homepage.virtuallyboring.com  CNAME  traefik.virtuallyboring.com
traefik.virtuallyboring.com   A      <your-public-ip>
```

If you only want LAN access (recommended for a dashboard), create the records in AD DNS only and skip Cloudflare.

### 5. Access

```
https://homepage.virtuallyboring.com
```

## Configuration

Homepage is configured via YAML files placed in `/mnt/SSD/Containers/homepage/`. On first run the directory is populated with defaults. Key files:

| File | Purpose |
|---|---|
| `services.yaml` | Define service tiles and API integrations |
| `bookmarks.yaml` | Quick-link bookmarks |
| `widgets.yaml` | Top-bar info widgets (date, search, etc.) |
| `settings.yaml` | Layout, theme, and general settings |
| `docker.yaml` | Docker socket integration for auto-discovery |

See the [Homepage documentation](https://gethomepage.dev) for full configuration reference.

## Allowed Hosts

The `HOMEPAGE_ALLOWED_HOSTS` environment variable is required to prevent DNS rebinding attacks. Behind Traefik, set it to just the hostname — no port needed since requests arrive on standard port 443:

```
HOMEPAGE_ALLOWED_HOSTS=homepage.virtuallyboring.com
```

If the value includes a port (e.g. `:3001`) Homepage will reject requests coming through Traefik and return a 403.

## Storage

| Data | Path |
|---|---|
| Configuration files | `/mnt/SSD/Containers/homepage` |
| Background images | `/mnt/SSD/Containers/homepage/images` |

## Maintenance

### Update image

```bash
docker compose pull
docker compose up -d
```

### Backup

```bash
docker compose down
tar -czf homepage-backup-$(date +%Y%m%d).tar.gz /mnt/SSD/Containers/homepage
docker compose up -d
```
