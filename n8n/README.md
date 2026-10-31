# n8n

[n8n](https://n8n.io) is a self-hostable workflow automation platform. It connects services via a node-based visual editor — think Zapier or Make, but running on your own infrastructure with no per-task pricing and full access to run custom code inside workflows.

Run it when you want to automate between internal services (Grafana alerts → Gotify, Gitea webhooks → Semaphore runs, NAS events → notifications), integrate with external APIs without building a custom app, or replace a paid automation SaaS with something you control.

Images in `compose.yaml` are frozen to the inventoried builds. See the [image update guide](../README.md#image-updates); `docker compose pull` alone does not upgrade them.

## Architecture

```text
Browser → Traefik (TLS + lan-only) → n8n :5678
                                          ↓
                                    n8n-postgres :5432
```

Two containers on a private `n8n` bridge network. Postgres is not exposed outside that network — only n8n can reach it. Traefik handles TLS termination and LAN-IP restriction.

n8n runs as the internal `node` user (UID/GID 1000). A root-created bind directory
does not inherit the image's ownership; prepare writable storage before startup.

## Prerequisites

Run Bash on the Linux host from `n8n/`. Deploy Traefik first.
For **fresh directories only**:

```bash
mkdir -p /mnt/SSD/Containers/n8n/{data,postgres}
chown 1000:1000 /mnt/SSD/Containers/n8n/data
```

For existing/restored data preserve ownership and ACLs. PostgreSQL manages its
own directory; do not chown it to the app user.

## Deployment

### 1. Configure environment

```bash
cp .env.example .env
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
| `/mnt/SSD/Containers/n8n/data` | App settings/key material and filesystem-backed binary data where configured |
| `/mnt/SSD/Containers/n8n/postgres` | Authoritative workflows, executions and encrypted credentials in PostgreSQL |

## Updating

n8n is pinned to the verified running `2.42.7` image plus its digest. Before
updating, review release notes and backups, then update the reviewed tag and
digest in `compose.yaml` (or review a Dependabot PR). From this directory,
deploy the selected image:

```bash
docker compose pull
docker compose up -d
```

n8n runs database migrations automatically on startup after an image update.

## Backup

Back up both directories consistently with **n8n and PostgreSQL stopped**, plus
the original image/Compose settings and encryption key. Follow the
[shared cold backup and restore procedure](../README.md#backing-up-data).
Do not use a hardcoded `pg_dump -U n8n n8n` if your configured account/database
differs. A logical SQL backup does not replace the app files/key.

Restore both paths to empty destinations with original versions/ownership and
the original encryption key. Start PostgreSQL before n8n; keep clients, webhook
senders and workflow triggers blocked during the drill. Verify saved credentials,
representative workflows and binary attachments before reopening. Do not rotate
the encryption key or run external-effect workflows simply to test recovery.
