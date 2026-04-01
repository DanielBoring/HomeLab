# Traefik

Traefik v3 reverse proxy with Docker provider and an optional Let's Encrypt TLS resolver. Exposes the Traefik dashboard and creates the shared `traefik` Docker network used by other services.

https://doc.traefik.io/traefik/getting-started/docker/

## Overview

| Setting | Value |
|---|---|
| Image | `traefik:v3.3` |
| HTTP port | 80 |
| HTTPS port | 443 |
| Dashboard | Enabled (insecure mode — internal access only) |
| Provider | Docker (auto-discovers containers via labels) |
| TLS | Optional — Let's Encrypt config commented out in `traefik.yml` |
| Certs storage | `/mnt/SSD/Containers/traefik/certs` |

## Prerequisites

Create the certs directory before deploying:

```bash
mkdir -p /mnt/SSD/Containers/traefik/certs
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

| Variable | Default | Description |
|---|---|---|
| `HTTP_PORT` | `80` | Host port for HTTP |
| `HTTPS_PORT` | `443` | Host port for HTTPS |
| `TZ` | `UTC` | Timezone (e.g. `America/New_York`) |
| `TRAEFIK_DOMAIN` | `traefik.localhost` | Hostname for the Traefik dashboard |

### 3. Deploy

```bash
docker compose up -d
```

### 4. Access the dashboard

```
http://<TRAEFIK_DOMAIN>/dashboard/
```

## Adding Services

To expose a container through Traefik, add labels to its `compose.yaml` and attach it to the `traefik` network:

```yaml
networks:
  traefik:
    external: true

services:
  my-service:
    networks:
      - traefik
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.my-service.rule=Host(`my-service.example.com`)"
      - "traefik.http.routers.my-service.entrypoints=websecure"
      - "traefik.http.routers.my-service.tls.certresolver=letsencrypt"
      - "traefik.http.services.my-service.loadbalancer.server.port=8080"
```

## Enabling Let's Encrypt TLS

Uncomment the `certificatesResolvers` block in [traefik.yml](traefik.yml) and fill in your email:

```yaml
certificatesResolvers:
  letsencrypt:
    acme:
      email: "your-email@example.com"
      storage: /letsencrypt/acme.json
      httpChallenge:
        entryPoint: web
```

Then update your router labels to use `entrypoints=websecure` and `tls.certresolver=letsencrypt`.

## Storage

| Data | Path |
|---|---|
| TLS certificates | `/mnt/SSD/Containers/traefik/certs` |

## Maintenance

### Update image

```bash
docker compose pull
docker compose up -d
```

### Reload configuration

Traefik automatically reloads when Docker labels change. To reload `traefik.yml` without restarting:

```bash
docker compose restart traefik
```
