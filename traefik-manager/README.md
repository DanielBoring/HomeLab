# traefik-manager

A self-hosted web UI for managing Traefik reverse proxy configuration without editing YAML files by hand. Supports adding/editing/removing HTTP routes, building middlewares from templates, viewing TLS certificate status, and creating timestamped backups of your dynamic config.

## Architecture

traefik-manager runs as a single container that:

- **Reads and writes** the Traefik dynamic config directory (`/mnt/SSD/Containers/traefik/dynamic`) — changes are picked up live by Traefik's `watch: true` file provider, so routes go active immediately without a Traefik restart.
- **Reads and writes** the static config (`traefik.yml`) for the Static Config and Plugins editors. The ACME `acme.json` remains read-only for displaying certificate expiry.
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
cp .env.example .env
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
| `STATIC_CONFIG_PATH` | `/app/traefik.yml` | Writable host static configuration for the Static Config and Plugins editors |

## Volumes

| Host Path | Container Path | Mode | Purpose |
|---|---|---|---|
| `/mnt/SSD/Containers/traefik/dynamic` | `/traefik-dynamic` | rw | Traefik dynamic config (routes, middlewares) |
| `/mnt/SSD/Containers/traefik-manager/config` | `/app/config` | rw | Manager settings and state |
| `/mnt/SSD/Containers/traefik-manager/backups` | `/app/backups` | rw | Timestamped config backups |
| `/mnt/SSD/Containers/traefik/certs/acme.json` | `/app/acme.json` | ro | Certificate data for the Certs tab |
| `/mnt/SSD/Containers/traefik/traefik.yml` | `/app/traefik.yml` | rw | Static Config and Plugins editors |

## Static Configuration Writes

Manager needs write access to the static configuration file. A read-only mount triggers its "Storage is not writable" banner even when the settings and backup volumes are writable. Changing host file permissions cannot override a read-only Docker mount.

After publishing this Compose change, redeploy the Manager stack to recreate the container with the writable mount; a container restart alone does not change mount permissions. Keep Traefik's own static-config mount and Manager's certificate mount read-only.

Edits made in Manager change `/mnt/SSD/Containers/traefik/traefik.yml`, not the copy in this repository. Copy intentional changes back into the repository to keep them in sync. Static configuration changes require restarting Traefik; this stack does not configure a Manager restart method, so restart Traefik separately after saving.
