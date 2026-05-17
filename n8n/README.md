# n8n

[n8n](https://n8n.io) is a self-hostable workflow automation platform. It connects services via a node-based visual editor — think Zapier or Make, but running on your own infrastructure with no per-task pricing and full access to run custom code inside workflows.

Run it when you want to automate between internal services (Grafana alerts → Gotify, Gitea webhooks → Semaphore runs, NAS events → notifications), integrate with external APIs without building a custom app, or replace a paid automation SaaS with something you control.

## Architecture

```
Browser → Traefik (TLS + lan-only) → n8n :5678
                                          ↓
                                    n8n-postgres :5432
```

Two containers on a private `n8n` bridge network. Postgres is not exposed outside that network — only n8n can reach it. Traefik handles TLS termination and LAN-IP restriction.

n8n runs as the internal `node` user (UID 1000). The data directory on the host will be owned by UID 1000 — this is expected and does not need manual `chown`.

## Prerequisites

```bash
mkdir -p /mnt/SSD/Containers/n8n/{data,postgres}
```

## Deployment

### 1. Configure environment

```bash
cp example.env .env
```

Generate the encryption key before starting — this value encrypts all credentials stored in workflows and **cannot be changed after first run** without making every saved credential unreadable:

```bash
openssl rand -hex 32
```

Paste the output into `N8N_ENCRYPTION_KEY` in `.env`. Store it somewhere safe (password manager, secret store).

| Variable | Description |
|---|---|
| `TZ` | Timezone (default: `America/New_York`) |
| `N8N_DOMAIN` | FQDN Traefik routes to n8n (e.g. `n8n.virtuallyboring.com`) |
| `N8N_PORT` | Host port for direct access (default: `5678`) |
| `N8N_ENCRYPTION_KEY` | AES encryption key for stored credentials — generate once, never change |
| `N8N_DB_NAME` | Postgres database name (default: `n8n`) |
| `N8N_DB_USER` | Postgres username (default: `n8n`) |
| `N8N_DB_PASSWORD` | Postgres password — set to a strong random value |

### 2. Start

```bash
docker compose up -d
docker compose logs -f n8n
```

Postgres starts first (n8n waits for its healthcheck). First boot takes ~30 seconds while n8n initialises the database schema.

### 3. Access

- **Via Traefik:** `https://<N8N_DOMAIN>` (LAN only)
- **Direct:** `http://<host-ip>:5678`

On first access n8n will prompt you to create an owner account. Complete this immediately — until an owner is registered the instance is unauthenticated.

## Storage

| Path | Contents |
|---|---|
| `/mnt/SSD/Containers/n8n/data` | Workflow definitions, execution logs, credentials (encrypted) |
| `/mnt/SSD/Containers/n8n/postgres` | PostgreSQL data directory |

## Updating

n8n is pinned to `latest`. To update to a new release:

```bash
docker compose pull
docker compose up -d
```

n8n runs database migrations automatically on startup after an image update.

## Backup

Back up both the data directory and the postgres database. The encryption key from `.env` is also required to restore credentials — include it in your backup strategy.

```bash
docker compose down

# Filesystem snapshot
tar -czf n8n-backup-$(date +%Y%m%d).tar.gz \
  /mnt/SSD/Containers/n8n/data \
  /mnt/SSD/Containers/n8n/postgres

docker compose up -d
```

For a consistent postgres dump instead of a filesystem copy:

```bash
docker exec n8n-postgres pg_dump -U n8n n8n > n8n-db-$(date +%Y%m%d).sql
```
