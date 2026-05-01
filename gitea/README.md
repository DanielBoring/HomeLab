# Gitea

Gitea is a self-hosted, lightweight Git service — think GitHub but running on your own hardware. It provides repository hosting, issue tracking, pull requests, CI/CD via Gitea Actions, a package registry, and a web-based code editor. It's written in Go, which means low memory usage (~150 MB at idle) and fast startup times.

**When does it make sense to run Gitea?**
- You want full control over your source code — no third-party has access
- You need private repositories without paying for a SaaS plan
- You want to mirror repositories from GitHub/GitLab for offline access or redundancy
- You're running a homelab CI/CD pipeline and want an on-prem trigger source
- You want to host packages (npm, Docker images, PyPI, etc.) alongside your code

## Architecture

```
Internet / LAN
      │
      ▼
  Traefik (HTTPS :443)
      │ Host(`gitea.yourdomain.com`)
      ▼
  gitea (port 3000) ──── gitea-db (PostgreSQL :5432)
      │
      ▼
  SSH (host :2222 → container :22)
```

- **gitea** — main application container. Serves the web UI, git-over-HTTPS, and SSH
- **gitea-db** — PostgreSQL 17 database on an internal `gitea` bridge network
- Web traffic goes through Traefik with TLS termination
- SSH is port-forwarded directly from the host (not proxied through Traefik)
- Both containers communicate over the internal `gitea` network; only `gitea` joins the external `traefik` network

## Prerequisites

Create the host directories before starting:

```bash
mkdir -p /mnt/SSD/Containers/gitea/data
mkdir -p /mnt/SSD/Containers/gitea/db
chown -R 3001:3001 /mnt/SSD/Containers/gitea
```

## Quick Start

1. Copy the env template and fill in your values:
   ```bash
   cp example.env .env
   $EDITOR .env
   ```

2. Generate secrets:
   ```bash
   # Secret key (cookie encryption)
   openssl rand -hex 32

   # Internal token
   openssl rand -hex 64
   ```

3. Start the stack:
   ```bash
   docker compose up -d
   ```

4. Open `https://<GITEA_DOMAIN>` in your browser. On first launch you'll see the **Installation** wizard. The database fields will be pre-filled from your env vars — scroll through and set the admin account, then click **Install Gitea**.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GITEA_DOMAIN` | Yes | Hostname Traefik routes to the web UI (e.g. `gitea.yourdomain.com`) |
| `GITEA_SSH_PORT` | Yes | Host port for SSH (default `2222`; host port 22 is usually the host OS) |
| `GITEA_DB_PASSWORD` | Yes | PostgreSQL password for the `gitea` user |
| `GITEA_SECRET_KEY` | Yes | 64-char hex key for cookie/session signing |
| `GITEA_INTERNAL_TOKEN` | Yes | 128-char hex token for internal API calls between Gitea processes |
| `PUID` / `PGID` | No | UID/GID the Gitea process runs as (default `3001`) |
| `TZ` | No | Timezone (default `America/New_York`) |

## SSH Clone URLs

By default, clone URLs will look like:

```
git clone git@gitea.yourdomain.com:user/repo.git   # SSH
git clone https://gitea.yourdomain.com/user/repo.git  # HTTPS
```

If you changed `GITEA_SSH_PORT` from `22`, git will include the port:

```
git clone ssh://git@gitea.yourdomain.com:2222/user/repo.git
```

You can add a `~/.ssh/config` entry to keep the short URL syntax:

```
Host gitea.yourdomain.com
    Port 2222
```

## Upgrading

```bash
docker compose pull
docker compose up -d
```

Gitea stores all repository data and configuration under `/mnt/SSD/Containers/gitea/data`, so the database and repos survive image upgrades. Always check the [Gitea changelog](https://github.com/go-gitea/gitea/releases) before upgrading across major versions.

## Traefik Note

The web UI is exposed publicly (no `lan-only` middleware) to allow remote git operations over HTTPS — pushing from a laptop off the LAN, webhooks from external CI runners, etc. If you only need LAN access, add `lan-only@file` to the middlewares label in `compose.yaml`. SSH bypasses Traefik entirely and is always reachable on `GITEA_SSH_PORT`.
