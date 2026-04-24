# Traefik

Traefik v3 reverse proxy with Docker provider and Let's Encrypt TLS via Cloudflare DNS challenge. Exposes the Traefik dashboard and creates the shared `traefik` Docker network used by other services.

https://doc.traefik.io/traefik/getting-started/docker/

## Overview

| Setting | Value |
|---|---|
| Image | `traefik:v3.3` |
| IP | `10.0.5.5` (macvlan — dedicated LAN IP) |
| HTTP port | 80 |
| HTTPS port | 443 |
| Metrics port | 8082 (Prometheus scrape) |
| Dashboard | `https://${TRAEFIK_DOMAIN}/dashboard/` (no auth) |
| Provider | Docker (auto-discovers containers via labels) |
| TLS | Let's Encrypt DNS challenge (Cloudflare) |
| Certs storage | `/mnt/SSD/Containers/traefik/certs` |

## Networking

Traefik runs on a **macvlan** network, giving it a dedicated LAN IP (`10.0.5.5`) separate from the Docker host. This means:

- Traefik binds to standard ports 80 and 443 on its own IP — no conflict with host ports
- Other containers use the `traefik` bridge network to be reached by Traefik (macvlan is only for external access)
- **The Docker host itself cannot reach macvlan IPs directly** — macvlan containers are isolated from their parent network interface. Access the Traefik dashboard from another machine on the LAN.

Three networks are used:

| Network | Type | Purpose |
|---|---|---|
| `traefik-macvlan` | macvlan | Traefik's dedicated LAN IP (`10.0.5.5`) |
| `traefik` | bridge | Shared by all services that Traefik reverse-proxies |
| `monitoring` | bridge (external) | Prometheus scrapes Traefik metrics on port `8082` |

## Prerequisites

Create the required directories and copy the config files to the host before deploying:

```bash
mkdir -p /mnt/SSD/Containers/traefik/certs
mkdir -p /mnt/SSD/Containers/traefik/dynamic

# Copy config files — these are mounted by absolute path, not served from the git working directory
cp traefik.yml /mnt/SSD/Containers/traefik/traefik.yml
cp dynamic/middlewares.yml /mnt/SSD/Containers/traefik/dynamic/middlewares.yml
```

> **Important:** `traefik.yml` does **not** expand environment variables. Values like `${EMAIL}` are treated as literal strings. Hardcode values (e.g. your email address) directly in the file.

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
| `TRAEFIK_DOMAIN` | `traefik.localhost` | Hostname for the Traefik dashboard |
| `TZ` | `America/New_York` | Container timezone |
| `CF_DNS_API_TOKEN` | — | Cloudflare API token (requires Zone:DNS:Edit + Zone:Zone:Read) |

### 3. Deploy

```bash
docker compose up -d
```

### 4. Add DNS records

In your Windows DNS server, add an A record pointing to Traefik's dedicated IP:

```
traefik.yourdomain.com  A  10.0.5.5
```

Each service you add behind Traefik gets a CNAME pointing to this A record:

```
myservice.yourdomain.com  CNAME  traefik.yourdomain.com
```

### 5. Access the dashboard

```
https://<TRAEFIK_DOMAIN>/dashboard/
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

## Let's Encrypt (DNS Challenge)

Certificates are issued automatically using Cloudflare DNS-01 challenge:

1. When a router requests a cert, Traefik calls the Cloudflare API to create a `_acme-challenge` TXT record in your zone
2. Let's Encrypt queries that TXT record to verify domain ownership
3. Traefik receives the cert and removes the TXT record
4. The cert is stored in `acme.json` and renewed automatically before expiry

This works without exposing port 80 publicly — unlike HTTP challenge, which requires a public-facing web server.

> **Gotcha — switching challenge types:** `acme.json` caches the ACME order state. If you ever change from HTTP challenge to DNS challenge (or vice versa), you must clear the file or Traefik will keep retrying the old challenge type and fail:
> ```bash
> truncate -s 0 /mnt/SSD/Containers/traefik/certs/acme.json
> chmod 600 /mnt/SSD/Containers/traefik/certs/acme.json
> docker compose restart traefik
> ```

## Dynamic Configuration

Shared middlewares and non-Docker routes live in `dynamic/middlewares.yml`, loaded via the file provider (`/etc/traefik/dynamic`). Traefik watches this directory and picks up changes automatically — no restart needed.

| Middleware | Purpose |
|---|---|
| `secure-headers@file` | Security headers (HSTS, X-Frame-Options, nosniff, referrer policy) |
| `lan-only@file` | IP allowlist — restricts access to `10.0.5.0/24` |

## Storage

| Data | Path |
|---|---|
| TLS certificates (`acme.json`) | `/mnt/SSD/Containers/traefik/certs` |
| Static config | `/mnt/SSD/Containers/traefik/traefik.yml` |
| Dynamic config (middlewares) | `/mnt/SSD/Containers/traefik/dynamic/` |

## Maintenance

### Update image

```bash
docker compose pull
docker compose up -d
```

### Update config files

After editing `traefik.yml` or `dynamic/middlewares.yml` in the repo, copy them to the host:

```bash
cp traefik.yml /mnt/SSD/Containers/traefik/traefik.yml
cp dynamic/middlewares.yml /mnt/SSD/Containers/traefik/dynamic/middlewares.yml
```

`dynamic/middlewares.yml` changes are picked up automatically. `traefik.yml` changes require a restart:

```bash
docker compose restart traefik
```

### Reload configuration

Traefik automatically reloads when Docker labels change. To reload `traefik.yml`:

```bash
docker compose restart traefik
```
