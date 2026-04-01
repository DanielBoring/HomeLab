# Homepage

A modern, self-hosted dashboard for your home lab. Displays service statuses, integrates with third-party APIs, and supports Docker auto-discovery.

## Overview

| Setting | Value |
|---|---|
| Image | `ghcr.io/gethomepage/homepage:latest` |
| Port | 3001 (maps to container port 3000) |
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

### 4. Access

```
http://<host-ip>:3001
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

The `HOMEPAGE_ALLOWED_HOSTS` environment variable is required to prevent DNS rebinding attacks. It is set in `compose.yaml` to match your domain and local IP. Update it if your hostname or IP changes:

```yaml
HOMEPAGE_ALLOWED_HOSTS: "*.yourdomain.com:3001, 10.0.x.x:3001"
```

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
