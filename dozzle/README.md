# Dozzle

Real-time Docker log viewer. Streams container logs to a browser UI via the Docker socket — stateless, no log storage.

## Services

| Service | Port | Description |
|---|---|---|
| dozzle | 8087 | Web UI (proxied via Traefik) |

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
| `DOZZLE_PORT` | `8087` | Host port (direct access only — Traefik ignores this) |

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

## Monitoring Remote Hosts (Agent Mode)

By default Dozzle only sees containers on the TrueNAS host it runs on (via the local Docker socket). To also monitor containers on remote hosts — such as Proxmox nodes — deploy a Dozzle agent on each remote host and point the central Dozzle instance at them.

### 1. Deploy an agent on each remote host

Run this on each Proxmox node (or any remote Docker host):

```bash
docker run -d \
  --name dozzle-agent \
  --restart unless-stopped \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -p 7007:7007 \
  amir20/dozzle:latest agent
```

Or as a compose service if you prefer:

```yaml
services:
  dozzle-agent:
    image: amir20/dozzle:latest
    container_name: dozzle-agent
    command: agent
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    ports:
      - 7007:7007
    healthcheck:
      test: ["CMD", "/dozzle", "healthcheck"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### 2. Connect the central Dozzle instance to the agents

Uncomment and populate `DOZZLE_REMOTE_AGENT` in `.env`:

```env
DOZZLE_REMOTE_AGENT=<PROXMOX_IP1>:7007,<PROXMOX_IP2>:7007,<PROXMOX_IP3>:7007
```

Then restart Dozzle:

```bash
docker compose up -d
```

All three Proxmox nodes will appear as selectable hosts in the Dozzle UI alongside the TrueNAS host.

### Notes

- Agent traffic on port `7007` is TLS-encrypted — no additional setup required.
- Restrict port `7007` to your LAN (`10.0.5.0/24`) on each Proxmox node's firewall so agents aren't reachable externally.
- Each agent only exposes its own host's containers — the central Dozzle instance aggregates the views.
- Set a `DOZZLE_HOSTNAME` on each remote agent by passing `-e DOZZLE_HOSTNAME=node1` to the `docker run` command (or the equivalent env var in compose) so hosts are clearly labeled in the UI.

---

## Starter Alerts

Alerts are configured in the Dozzle UI under **Alerts** and persist in the `/data` volume. Each alert has a **Container Expression** (which containers to watch) and a **Trigger Expression** (what to match). When no container expression is needed for all containers, use `name != ""`.

### Event Alerts

Fire on Docker engine events — most reliable signal for container health, independent of log format.

| Name | Container Expression | Trigger Expression |
|---|---|---|
| Container OOM killed | `name != ""` | `name == "oom"` |
| Container died | `name != ""` | `name == "die"` |
| Container restarting | `name != ""` | `name == "restart"` |

### Log Alerts

| Name | Container Expression | Trigger Expression |
|---|---|---|
| Traefik backend errors | `name == "traefik"` | `message contains "level=error"` |
| Traefik DNS failure | `name == "traefik"` | `message contains "no such host"` |
| Database errors | `name contains "db"` | `message contains "ERROR" && message contains "Table"` |
| Semaphore task failed | `name == "semaphore"` | `message contains "Task failed"` |

### Metric Alerts

| Name | Container Expression | Trigger Expression | Notes |
|---|---|---|---|
| High CPU | `name != ""` | `cpu > 85` | Set cooldown 10+ min |
| High memory | `name != ""` | `memory > 90` | Set cooldown 10+ min |

### Tips

- **Set a 10+ minute cooldown on metric alerts** to avoid Discord spam during backups or scans
- Alert configs are stored in `/mnt/SSD/Containers/dozzle` and survive container restarts

---

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
