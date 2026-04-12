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

## How Docker Labels Work

Traefik reads labels attached to Docker containers and automatically builds routes from them — no central config file to edit every time you add a service. This is called **dynamic configuration**.

### Label anatomy

Every Traefik label follows one of these patterns:

```
traefik.http.routers.<NAME>.<PROPERTY>=<VALUE>
traefik.http.services.<NAME>.<PROPERTY>=<VALUE>
traefik.http.middlewares.<NAME>.<TYPE>.<PROPERTY>=<VALUE>
```

`<NAME>` is a string **you choose** — pick something that matches the service (e.g. `portainer`, `grafana`). It ties the router, service, and middleware definitions together for that container. It has no effect outside of that container's labels.

### The minimum four labels

These are the only labels you need to get a container behind Traefik with HTTPS:

```yaml
labels:
  - "traefik.enable=true"
  # 1. Opt this container in (required because exposedByDefault is false)

  - "traefik.http.routers.myapp.rule=Host(`myapp.yourdomain.com`)"
  # 2. Route requests for this hostname to this container

  - "traefik.http.routers.myapp.entrypoints=websecure"
  # 3. Listen on the HTTPS entrypoint (port 443)

  - "traefik.http.routers.myapp.tls.certresolver=letsencrypt"
  # 4. Automatically get a Let's Encrypt cert for this hostname
```

> **Note:** The HTTP → HTTPS redirect is global (configured in `traefik.yml`), so you don't need a redirect middleware on each service — it's automatic.

### When to add a port label

Traefik auto-detects the container's port when only one is exposed. If the container exposes **multiple ports**, Traefik won't know which to use and you must specify it:

```yaml
  - "traefik.http.services.myapp.loadbalancer.server.port=8080"
```

Check with `docker inspect <container>` — if you see more than one entry under `ExposedPorts`, add this label.

### When to add a network label

If a container is on **multiple Docker networks**, Traefik needs to know which one to use to reach it. Without this label it may pick the wrong network and return a 502:

```yaml
  - "traefik.docker.network=traefik"
```

Rule of thumb: add this whenever a container has both the `traefik` network and at least one other (e.g. a `backend` database network).

### When to add a scheme label

Some containers serve HTTPS internally (e.g. Portainer on port 9443). If you send plain HTTP to them you'll get a connection error. Tell Traefik to speak HTTPS to the backend:

```yaml
  - "traefik.http.services.myapp.loadbalancer.server.scheme=https"
```

### Attaching shared middlewares

Middlewares defined in [`dynamic/middlewares.yml`](dynamic/middlewares.yml) are referenced with the `@file` suffix. Chain multiple with a comma:

```yaml
  - "traefik.http.routers.myapp.middlewares=secure-headers@file"
  # or
  - "traefik.http.routers.myapp.middlewares=secure-headers@file,lan-only@file"
```

| Middleware | When to use |
|---|---|
| `secure-headers@file` | Any public-facing service |
| `lan-only@file` | Admin UIs that should never be reachable from outside your LAN |

### How Traefik processes a request

```
1. Request arrives at port 443 (websecure entrypoint)
2. Traefik checks all routers for a matching rule  →  Host(`myapp.yourdomain.com`)
3. Matched router runs any attached middlewares    →  secure-headers, lan-only, etc.
4. Request is forwarded to the container's port
5. Container responds, Traefik sends it back to the client
```

### Full example with all options

```yaml
services:
  myapp:
    image: myapp:latest
    networks:
      - backend     # Private network for a database
      - traefik     # Traefik network for external access
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.myapp.rule=Host(`myapp.yourdomain.com`)"
      - "traefik.http.routers.myapp.entrypoints=websecure"
      - "traefik.http.routers.myapp.tls.certresolver=letsencrypt"
      - "traefik.http.routers.myapp.middlewares=secure-headers@file"
      - "traefik.http.services.myapp.loadbalancer.server.port=8080"
      - "traefik.docker.network=traefik"   # needed because container is on two networks

networks:
  backend:
  traefik:
    external: true
```

### Troubleshooting labels

The Traefik dashboard (`traefik.yourdomain.com`) is the fastest way to debug:

- **Routers tab** — confirms your router exists and shows its rule, entrypoint, and status (green = healthy)
- **Services tab** — shows the IP and port Traefik is forwarding to
- **Middlewares tab** — confirms `@file` middlewares loaded from `dynamic/middlewares.yml`

If a service doesn't appear at all, the container is missing `traefik.enable=true` or isn't on the `traefik` network.

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
