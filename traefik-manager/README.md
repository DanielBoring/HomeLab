# traefik-manager

A self-hosted web UI for managing Traefik reverse proxy configuration without editing YAML files by hand. Supports adding/editing/removing HTTP routes, building middlewares from templates, viewing TLS certificate status, and creating timestamped backups of your dynamic config.

## Architecture

traefik-manager runs as a single container that:

- **Reads and writes** the Traefik dynamic config directory (`/mnt/SSD/Containers/traefik/dynamic`) — changes are picked up live by Traefik's `watch: true` file provider, so routes go active immediately without a Traefik restart.
- **Reads (read-only)** the static config (`traefik.yml`) to display plugins and the ACME `acme.json` to display certificate expiry.
- **Queries the Traefik API** at `http://traefik:8080` to show live router counts and service health — this requires `api.insecure: true` in `traefik.yml` (see Prerequisites).

```
Browser → Traefik (websecure:443) → traefik-manager:5000
                                          ↕ read/write
                         /mnt/SSD/Containers/traefik/dynamic/
                                          ↕ watch: true
                                       Traefik
```

## Prerequisites

### Enable the Traefik API on port 8080

traefik-manager connects to `http://traefik:8080`. This requires `api.insecure: true` in `traefik/traefik.yml`:

```yaml
api:
  dashboard: true
  insecure: true   # exposes API on port 8080 — LAN-accessible via macvlan IP
```

Port 8080 will be reachable on the macvlan LAN IP (`10.0.5.5:8080`) and from other containers on the `traefik` Docker bridge network. It is not exposed to the internet.

### Create host directories

```bash
mkdir -p /mnt/SSD/Containers/traefik-manager/{config,backups}
```

## Deployment

```bash
cp example.env .env
# edit .env with your domain
docker compose up -d
```

On first start, a temporary admin password is printed to the container logs:

```bash
docker logs traefik-manager | grep -i password
```

Navigate to `https://${TRAEFIK_MANAGER_DOMAIN}` and complete the setup wizard.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `TRAEFIK_MANAGER_DOMAIN` | Yes | Public domain for this service (e.g. `traefik-manager.virtuallyboring.com`) |

The following are hardcoded in `compose.yaml` since they are environment-wide constants:

| Variable | Value | Description |
|---|---|---|
| `DOMAINS` | `virtuallyboring.com` | Base domain shown in the route builder |
| `CERT_RESOLVER` | `letsencrypt` | Default ACME resolver for new routes |
| `TRAEFIK_API_URL` | `http://traefik:8080` | Traefik API endpoint (requires `api.insecure: true`) |
| `COOKIE_SECURE` | `true` | Required for HTTPS session cookies |
| `CONFIG_DIR` | `/traefik-dynamic` | Maps to `/mnt/SSD/Containers/traefik/dynamic` |

## Volumes

| Host Path | Container Path | Mode | Purpose |
|---|---|---|---|
| `/mnt/SSD/Containers/traefik/dynamic` | `/traefik-dynamic` | rw | Traefik dynamic config (routes, middlewares) |
| `/mnt/SSD/Containers/traefik-manager/config` | `/app/config` | rw | Manager settings and state |
| `/mnt/SSD/Containers/traefik-manager/backups` | `/app/backups` | rw | Timestamped config backups |
| `/mnt/SSD/Containers/traefik/certs/acme.json` | `/app/acme.json` | ro | Certificate data for the Certs tab |
| `/mnt/SSD/Containers/traefik/traefik.yml` | `/app/traefik.yml` | ro | Static config for the Plugins tab |
