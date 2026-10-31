# Heimdall

Heimdall is a browser homepage and application dashboard — a single page of tiles linking to all your self-hosted services, with optional live status checks and API integrations for supported apps (called "Enhanced" apps). It's intentionally minimal: no agents, no Docker socket access, no separate database server — just a PHP/nginx app with SQLite persistence.

**When to use this over alternatives like Homepage or Homarr:** Heimdall is the lowest-friction option. If you want tiles on a page and nothing more, it's the right choice. Homepage is better if you want live stats pulled directly from service APIs (Sonarr queue depth, Grafana metrics, etc.) and are comfortable writing YAML config files. Homarr sits in the middle with a drag-and-drop UI and more integrations.

[LinuxServer image documentation](https://docs.linuxserver.io/images/docker-heimdall/)

## Architecture

```text
Browser (HTTPS) → Traefik (TLS termination) → heimdall:80 (nginx/PHP-FPM)
```

Heimdall is a standard nginx + PHP-FPM app. No external dependencies. Configuration and the SQLite database live in `/config`.

## Prerequisites

- Traefik running and the `traefik` external network created
- Host storage directory created on TrueNAS:
  ```sh
  mkdir -p /mnt/SSD/Containers/heimdall
  ```
- DNS record for `heimdall.yourdomain.com` pointing to Traefik's IP (`10.0.5.5`)

## Quick Start

```sh
cp .env.example .env
docker compose up -d
```

Navigate to `https://heimdall.yourdomain.com` — no login required by default. To add password protection, see below.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TZ` | `America/New_York` | Container timezone |
| `PUID` | `3001` | User ID for file permissions |
| `PGID` | `3001` | Group ID for file permissions |
| `HEIMDALL_DOMAIN` | — | Public hostname for Traefik routing |
| `ALLOW_INTERNAL_REQUESTS` | `false` | Allow Enhanced apps to reach LAN/private IPs |

### ALLOW_INTERNAL_REQUESTS

Heimdall's Enhanced app integrations (e.g. Sonarr, Radarr, Pi-hole) make server-side HTTP requests to fetch live data. By default these are blocked for private IP ranges as a security measure. Set to `true` if your services are on a LAN IP and you want live stats to work.

## Password Protection

Optional additional HTTP basic auth is handled by nginx and configured after first start:

```sh
# Create the htpasswd file inside the container
docker exec -it heimdall htpasswd -c /config/nginx/.htpasswd <username>
```

Then edit `/mnt/SSD/Containers/heimdall/nginx/site-confs/default.conf` and uncomment the two basic auth lines:

```nginx
auth_basic "Restricted";
auth_basic_user_file /config/nginx/.htpasswd;
```

Restart the container to apply: `docker compose restart heimdall`.

The `lan-only` route limits allowed source addresses, not application identity;
verify actual ingress/firewall behavior rather than assuming internet isolation.
`htpasswd -c` creates/replaces the password file: preserve an existing file and
omit `-c` when adding another user.

## Operations and recovery

Run Linux commands from `heimdall/`; give PUID/PGID access to fresh storage and
retain existing ACLs. Verify `docker compose ps`, recent `heimdall` logs and
dashboard tiles. Enabling `ALLOW_INTERNAL_REQUESTS` permits server-side LAN
requests; only trusted users should configure integrations.

Stop writers before preserving the complete config path (SQLite, tiles, nginx
auth config and integration credentials) with original images/settings. Follow
the [shared recovery procedure](../README.md#backing-up-data), restore privately
at the same version and check tiles/auth before enabling API integrations.
Review the selected release's migrations before replacing the moving image.
