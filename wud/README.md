# What's Up Docker (WUD)

[WUD](https://github.com/getwud/wud) watches your running containers and notifies you when a newer image is available. It's a passive observer by default — it won't touch your containers unless you explicitly configure an update trigger.

Run it instead of Watchtower when you want to know about updates but apply them yourself. WUD gives you a dashboard showing what's outdated and by how much, sends notifications to Discord (or wherever), and optionally can trigger updates automatically per-container if you want that level of automation.

## Architecture

```
Docker socket (read-only) → WUD → Discord webhook
                              ↓
                         Web dashboard :3000
                         (via Traefik, LAN only)
```

WUD polls on a cron schedule (`WUD_WATCHER_LOCAL_CRON`, default hourly). When it detects a newer image tag it fires the configured triggers — in this setup, a Discord notification.

## Prerequisites

- Traefik running with the `traefik` external network created
- Host directory and Discord webhook URL

```bash
sudo mkdir -p /mnt/SSD/Containers/wud
```

Create a Discord webhook: **Server Settings → Integrations → Webhooks → New Webhook**, copy the URL.

## Deployment

### 1. Configure environment

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `TZ` | Timezone (default: `America/New_York`) |
| `WUD_DOMAIN` | FQDN Traefik routes to WUD (e.g. `wud.virtuallyboring.com`) |
| `WUD_PORT` | Host port for direct access (default: `3010`) |
| `WUD_DISCORD_WEBHOOK_URL` | Discord webhook URL for notifications |

### 2. Start

```bash
docker compose up -d
docker compose logs -f wud
```

### 3. Access

- **Via Traefik:** `https://<WUD_DOMAIN>` (LAN only)
- **Direct:** `http://<host-ip>:3010`

## Controlling What Gets Watched

By default WUD watches every container. Opt individual containers out with a label:

```yaml
labels:
  - "wud.watch=false"
```

Or pin a container to only notify on specific tags using a regex:

```yaml
labels:
  - "wud.tag.include=^\\d+\\.\\d+\\.\\d+$"   # semver only, ignore latest/edge/etc
```

## Auto-Update Triggers (Optional)

WUD is configured read-only by default — it notifies but does not act. To enable auto-updates for specific containers, two changes are needed:

1. Remove `:ro` from the Docker socket mount in `compose.yaml`
2. Add the trigger env var and a label on the containers you want auto-updated:

```yaml
# In wud/compose.yaml environment:
- WUD_TRIGGER_DOCKER_LOCAL_PRUNE=true

# On the container you want auto-updated:
labels:
  - "wud.trigger=docker"
```

Use this carefully — auto-updating production-ish services like Traefik or databases without testing first can cause outages.

## Portainer Integration

WUD has no native Portainer trigger, but Portainer exposes a **stack webhook** that redeploys a stack when POSTed to. WUD's HTTP trigger can POST to that URL the moment it detects an update — giving you automated redeploys driven by Portainer rather than raw Docker API calls.

This is the safer auto-update path: Portainer handles the pull and redeploy using the same mechanism as clicking "Redeploy" in the UI, with the full stack context (env vars, volumes, networks) already configured there.

### 1. Enable the webhook in Portainer

In Portainer, open the stack you want to auto-update and go to **Stack → Edit → Stack webhook**. Enable it and copy the webhook URL — it looks like:

```
https://portainer.virtuallyboring.com/api/stacks/webhooks/<uuid>
```

Repeat for each stack you want WUD to trigger.

### 2. Add the HTTP trigger to WUD

Add one env var per stack to `compose.yaml` (or `.env`). The trigger name is arbitrary — use something that matches the stack:

```yaml
# In wud/compose.yaml environment:
- WUD_TRIGGER_HTTP_ARRSTACK_URL=${WUD_PORTAINER_WEBHOOK_ARRSTACK}
- WUD_TRIGGER_HTTP_NEXTCLOUD_URL=${WUD_PORTAINER_WEBHOOK_NEXTCLOUD}
```

And the corresponding `.env` entries:

```env
WUD_PORTAINER_WEBHOOK_ARRSTACK=https://portainer.virtuallyboring.com/api/stacks/webhooks/<uuid>
WUD_PORTAINER_WEBHOOK_NEXTCLOUD=https://portainer.virtuallyboring.com/api/stacks/webhooks/<uuid>
```

### 3. Label the containers to wire them up

On each container in a Portainer-managed stack, add a label telling WUD which trigger to fire when that container has an update. Use `wud.trigger` with a comma-separated list if you want both a Discord notification and a Portainer redeploy:

```yaml
labels:
  - "wud.trigger=discord,http.arrstack"    # notify Discord AND trigger Portainer redeploy
  # or just:
  - "wud.trigger=http.arrstack"            # Portainer redeploy only, no Discord message
```

### Notes

- The Portainer webhook redeploys the **entire stack**, not just the one updated container — all services in the stack get restarted
- Don't use this for stacks containing databases unless you're comfortable with the restart window
- The Docker socket `:ro` mount is fine — WUD never touches Docker directly with this approach, Portainer does

## Updating

WUD uses a floating `latest` tag by default. To update:

```bash
docker compose pull
docker compose up -d
```
