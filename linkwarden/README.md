# Linkwarden

Self-hosted bookmark manager. Saves links with full-page snapshots, PDFs, and readable text archives so bookmarks survive link rot. Supports collections, tags, and sharing — works as a team tool or a personal read-later list.

Run it when you want bookmarks that outlast the pages they point to and don't live in a browser profile tied to one machine.

Images in `compose.yaml` are frozen to the inventoried builds. See the [image update guide](../README.md#image-updates); `docker compose pull` alone does not upgrade them.

## Architecture

```
Browser / API clients
        │
        ▼
   Traefik (TLS)
        │
        ▼
  linkwarden:3000  ──── linkwarden-db (PostgreSQL 16)
        │
        ▼
  /data/data  (screenshots, PDFs, archives)
```

| Service | Port | Description |
|---|---|---|
| app | 3000 | Next.js web UI and REST API (proxied via Traefik) |
| db | internal | PostgreSQL 16 — all bookmark metadata and user data |

`db` is on an isolated `linkwarden` bridge network. Only `app` is connected to the `traefik` network.

## Prerequisites

### 1. Create storage directories

```bash
mkdir -p /mnt/SSD/Containers/linkwarden/{db,data}
```

PostgreSQL and the app both run as internal container users — no `chown` needed.

### 2. Generate secrets

```bash
# Postgres password — must be hex; base64 contains +/= which break the DATABASE_URL
openssl rand -hex 32

# NextAuth secret
openssl rand -base64 32
```

Paste the outputs into `.env`.

## Quick Start

```bash
cp .env.example .env
# Edit .env — fill in LINKWARDEN_DOMAIN, POSTGRES_PASSWORD, NEXTAUTH_SECRET
docker compose up -d
docker compose logs -f app
```

First startup runs database migrations automatically. Navigate to `https://<LINKWARDEN_DOMAIN>` and create your account — the first registered user becomes admin.

> **Note:** Registration is open by default. Set `DISABLE_REGISTRATION=true` in the app environment after creating your account if this is a personal instance.

## Configuration

| Variable | Required | Description |
|---|---|---|
| `LINKWARDEN_DOMAIN` | Yes | Hostname Traefik routes to Linkwarden |
| `TZ` | No | Timezone (default: `America/New_York`) |
| `POSTGRES_USER` | Yes | PostgreSQL username |
| `POSTGRES_PASSWORD` | Yes | PostgreSQL password — generate with `openssl rand -base64 32` |
| `POSTGRES_DB` | Yes | PostgreSQL database name |
| `NEXTAUTH_SECRET` | Yes | NextAuth signing secret — generate with `openssl rand -base64 32` |

`DATABASE_URL` and `NEXTAUTH_URL` are derived automatically in `compose.yaml` from the above variables — do not add them to `.env`.

## Storage

| Data | Host Path |
|---|---|
| Screenshots, PDFs, readable archives | `/mnt/SSD/Containers/linkwarden/data` |
| PostgreSQL data | `/mnt/SSD/Containers/linkwarden/db` |

## Maintenance

### Update images

```bash
docker compose pull
docker compose up -d
docker compose logs -f app
```

### Backup

```bash
docker compose down
tar -czf linkwarden-backup-$(date +%Y%m%d).tar.gz \
  /mnt/SSD/Containers/linkwarden
docker compose up -d
```

### Restore

Restore first to an isolated host with the same application and PostgreSQL versions. Verify the archive and encrypted environment backup before downtime. Do not delete the current database or archived content; preserve it for rollback. On the Linux host, replace the backup filename below with your verified archive:

```bash
tar -tzf /path/to/linkwarden-backup.tar.gz
docker compose down
mv /mnt/SSD/Containers/linkwarden "/mnt/SSD/Containers/linkwarden.pre-restore-$(date +%Y%m%d-%H%M%S)"
tar -xzf /path/to/linkwarden-backup.tar.gz -C /
docker compose up -d
```

Preserve numeric ownership from the archive, verify login and archived content, and retain the old directory until recovery is confirmed. If extraction fails, leave the stack stopped rather than initializing a new empty instance.
