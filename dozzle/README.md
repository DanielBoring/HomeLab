# Dozzle

Real-time Docker log viewer. Streams container logs to a browser UI via the Docker socket — stateless, no log storage.

## Services

| Service | Port | Description |
|---|---|---|
| dozzle | 8080 | Web UI (proxied via Traefik) |

## Prerequisites

No persistent storage directory needed — Dozzle is stateless. The `/data` volume only stores user settings and alert configs. It is created automatically by Docker as a named volume bound to:

```
/mnt/SSD/Containers/dozzle
```

Create it before deploying:

```bash
mkdir -p /mnt/SSD/Containers/dozzle
```

## Quick Start

```bash
cp .env.example .env
# Edit .env — set DOZZLE_DOMAIN at minimum
docker compose up -d
```

### Verify

```bash
docker compose ps
docker compose logs -f
```

Navigate to `https://<DOZZLE_DOMAIN>` to access the web UI.

## Configuration

`.env` variables:

| Variable | Default | Description |
|---|---|---|
| `TZ` | `America/New_York` | Timezone |
| `DOZZLE_HOSTNAME` | `homelab` | Display name for this host in the UI |
| `DOZZLE_AUTH_PROVIDER` | `none` | Auth mode: `none`, `simple`, `forward-proxy` |
| `DOZZLE_DOMAIN` | `dozzle.localhost` | Hostname Traefik routes to Dozzle |
| `DOZZLE_PORT` | `8080` | Host port (direct access only — Traefik ignores this) |

Commented-out options in `compose.yaml`:

| Variable | Description |
|---|---|
| `DOZZLE_AUTH_TTL` | Persist auth sessions (e.g. `48h`) — requires `DOZZLE_AUTH_PROVIDER=simple` |
| `DOZZLE_ENABLE_ACTIONS` | Allow start/stop/restart from UI — requires removing `:ro` from socket mount |
| `DOZZLE_ENABLE_SHELL` | Allow shell access to containers — requires removing `:ro` from socket mount |
| `DOZZLE_REMOTE_AGENT` | Connect to remote Dozzle agents (e.g. `host1:7007,host2:7007`) |
| `DOZZLE_FILTER` | Limit visible containers by name or label (e.g. `name=myapp*`) |
| `DOZZLE_LEVEL` | Log verbosity: `debug`, `info`, `warn`, `error` |

## Storage

| Data | Path |
|---|---|
| User settings and alert configs | `/mnt/SSD/Containers/dozzle` |

## Portainer Integration

Portainer and Dozzle complement each other naturally — Portainer handles container management (deploy, start/stop, inspect) while Dozzle handles real-time log streaming. Both mount the Docker socket read-only and coexist without conflict.

### Configure Portainer to Open Logs in Dozzle

Portainer CE/BE supports an **External Log Viewer** setting that adds a link on each container's log page, opening that container directly in Dozzle.

1. In Portainer, go to **Settings → General**.
2. Scroll to **Log Viewer** and enable **External Log Viewer**.
3. Set the URL to:
   ```
   https://<DOZZLE_DOMAIN>/show?name={containerName}
   ```
   Replace `<DOZZLE_DOMAIN>` with your actual Dozzle domain (e.g. `dozzle.example.com`). The `{containerName}` placeholder is filled in by Portainer at click time.
4. Save settings.

Once configured, container log pages in Portainer will show an **Open in external log viewer** link that jumps directly to that container's live log stream in Dozzle.

### Notes

- The redirect happens in the browser — Portainer and Dozzle do not need to be on the same Docker network for this to work.
- If Dozzle has authentication enabled (`DOZZLE_AUTH_PROVIDER=simple` or `forward-proxy`), the browser will be prompted to log in before the log view loads.
- Dozzle resolves container names to IDs at request time. If a container was recently recreated, the link still works as long as the name is unchanged.

---

## Maintenance

### Update image

```bash
docker compose pull
docker compose up -d
```

### Enable Simple Auth

1. Generate a user entry:
   ```bash
   docker run -it --rm amir20/dozzle generate admin --password yourpassword --email you@example.com
   ```
2. Paste the output into `/mnt/SSD/Containers/dozzle/users.yml`
3. Set `DOZZLE_AUTH_PROVIDER=simple` in `.env` and restart:
   ```bash
   docker compose up -d
   ```
