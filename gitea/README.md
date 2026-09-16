# Gitea on TrueNAS (Portainer)

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

## What this stack does

- Routes `https://gitea.virtuallyboring.com` through the existing Traefik
  network, with the existing `secure-headers@file` and `lan-only@file`
  middlewares. It is not Internet-accessible through Traefik.
- Publishes Git-over-SSH on TrueNAS TCP port `2222`. This is separate from
  Traefik and is reachable wherever the TrueNAS host is reachable; restrict it
  with host firewall rules if SSH must also be LAN-only.
- Stores Gitea repositories/configuration and PostgreSQL data on the SSD bind
  paths below. Neither is a named Docker-managed volume.
- Disables self-service registration. Create the administrator in the first-run
  wizard, then use that account to invite users.

## Prerequisites

Create the host directories before starting:

```bash
mkdir -p /mnt/SSD/Containers/gitea/data
mkdir -p /mnt/SSD/Containers/gitea/db
```

The initial containers create the required ownership inside these directories.
Do not populate either directory with files from another Gitea/PostgreSQL
installation.

Confirm that no non-Docker service owns the planned SSH port:

```bash
ss -ltnp '( sport = :2222 )'
```

At preparation time, Portainer reported that no running Docker container on
`TrueNAS.virtuallyboring.com` publishes TCP port 2222.

## Quick Start

1. Copy the environment template and replace every `replace-with-...` value:
   ```bash
   cp .env.example .env
   $EDITOR .env
   ```

2. Generate secrets:
   ```bash
   # Secret key (cookie encryption)
   openssl rand -hex 32

   # Internal token
   openssl rand -hex 64
   ```

3. In Portainer, select the `TrueNAS.virtuallyboring.com` environment and
   create a new **Git repository** stack from this repository. Set the Compose
   path to `gitea/compose.yaml`, add the values from `.env` as stack environment
   variables, then deploy. If deploying from the TrueNAS shell instead, run:
   ```bash
   docker compose up -d
   ```

4. Open `https://gitea.virtuallyboring.com` from the LAN. On first launch, use
   the **Installation** wizard to create the administrator and click **Install
   Gitea**. The database settings are supplied by Compose; do not expose port
   5432 or change its host to `localhost`.

5. Verify the Gitea container is healthy in Portainer, then clone a test
   repository over HTTPS and SSH. With the configured non-standard SSH port:

   ```bash
   git clone ssh://git@gitea.virtuallyboring.com:2222/<owner>/<repo>.git
   ```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GITEA_DOMAIN` | Yes | `gitea.virtuallyboring.com`; create a LAN DNS record pointing to Traefik |
| `GITEA_SSH_PORT` | Yes | Host port for SSH (default `2222`; host port 22 is usually the host OS) |
| `GITEA_DB_PASSWORD` | Yes | PostgreSQL password for the `gitea` user |
| `GITEA_SECRET_KEY` | Yes | 64-char hex key for cookie/session signing |
| `GITEA_INTERNAL_TOKEN` | Yes | 128-char hex token for internal API calls between Gitea processes |
| `GITEA_DISABLE_REGISTRATION` | No | Defaults to `true`; prevents LAN users from self-registering |
| `PUID` / `PGID` | No | UID/GID the Gitea process runs as (default `3001`) |
| `TZ` | No | Timezone (default `America/New_York`) |

## SSH Clone URLs

Clone URLs will look like:

```
git clone ssh://git@gitea.virtuallyboring.com:2222/user/repo.git
git clone https://gitea.virtuallyboring.com/user/repo.git
```

You can add an `~/.ssh/config` entry to keep the short SSH URL syntax:

```
Host gitea.virtuallyboring.com
    Port 2222
```

## Upgrading

```bash
docker compose pull
docker compose up -d
```

Gitea stores all repository data and configuration under `/mnt/SSD/Containers/gitea/data`, so the database and repos survive image upgrades. Always check the [Gitea changelog](https://github.com/go-gitea/gitea/releases) before upgrading across major versions.

## Backup and recovery

Back up both `/mnt/SSD/Containers/gitea/data` and
`/mnt/SSD/Containers/gitea/db` together. Gitea repositories live in the data
path, but issues, users, permissions, and settings live in PostgreSQL. A backup
of only one path is not a complete restore point.
