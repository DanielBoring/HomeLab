# OwnCloud Infinite Scale (OCIS)

OwnCloud Infinite Scale is the modern, ground-up rewrite of OwnCloud — built in Go as a set of microservices bundled into a single binary/container. Unlike the classic OwnCloud 10 (PHP + MariaDB), OCIS requires no external database. It stores files on the local POSIX filesystem, manages users via a built-in LDAP directory (LibreGraph IDM), and uses JWT for all internal service-to-service auth.

**Why run OCIS instead of Nextcloud?** OCIS is significantly lighter, starts faster, and has lower operational overhead (no DB to manage). The trade-off is a smaller app ecosystem — OCIS does not have Nextcloud's breadth of first-party apps. It's a strong fit if you want self-hosted file sync/share without the complexity.

## Architecture

```
Browser / Desktop Sync Client
        │ HTTPS
        ▼
   Traefik (TLS termination, letsencrypt cert)
        │ HTTP
        ▼
  ocis container :9200
  ┌─────────────────────────────────────────┐
  │  PROXY service  ←  all incoming traffic │
  │  IDM (LibreGraph LDAP)                  │
  │  IDP (built-in OIDC provider)           │
  │  STORAGE-USERS (POSIX decomposed FS)    │
  │  THUMBNAILS, SEARCH, AUDIT, …          │
  └─────────────────────────────────────────┘
        │
  /var/lib/ocis  →  /mnt/SSD/Containers/ocis/data
  /etc/ocis      →  /mnt/SSD/Containers/ocis/config
```

`PROXY_TLS=false` tells the built-in proxy to accept plain HTTP — Traefik handles TLS. The `OCIS_URL` env var tells OCIS its own public HTTPS address so OIDC redirects and share links resolve correctly.

`ocis init` runs on the first container start and writes `/etc/ocis/ocis.yaml` with hashed admin password and generated secrets. The `|| true` in the entrypoint command means subsequent starts skip init silently.

## Host Prerequisites

OCIS runs as UID 1000 internally. The bind-mounted host directories must be owned by that UID before the first start, or OCIS will fail to write config/data:

```bash
mkdir -p /mnt/SSD/Containers/ocis/{config,data}
chown -R 1000:1000 /mnt/SSD/Containers/ocis
```

## Quick Start

1. Create host directories and set ownership (see above).
2. Copy `example.env` → `.env` and fill in all values.
3. Generate secrets if you want them pre-set:
   ```bash
   openssl rand -hex 32  # run three times — JWT, transfer, machine auth
   ```
4. Deploy:
   ```bash
   docker compose up -d
   ```
5. Tail logs to confirm init succeeded and all services started:
   ```bash
   docker compose logs -f ocis
   ```
6. Log in at `https://<OCIS_DOMAIN>` with username `admin` and the password from `OCIS_ADMIN_PASSWORD`.

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `OCIS_DOMAIN` | yes | — | Public hostname (e.g. `cloud.yourdomain.com`) |
| `OCIS_ADMIN_PASSWORD` | yes (first run) | — | Initial admin password; ignored after `ocis init` runs |
| `OCIS_JWT_SECRET` | no | auto-generated | JWT signing key; pre-set for recoverability |
| `OCIS_TRANSFER_SECRET` | no | auto-generated | File transfer secret; pre-set for recoverability |
| `OCIS_MACHINE_AUTH_API_KEY` | no | auto-generated | Machine-to-machine auth key; pre-set for recoverability |
| `TZ` | no | `America/New_York` | Timezone |
| `OCIS_LOG_LEVEL` | no | `warn` | Log verbosity (`debug`, `info`, `warn`, `error`) |

## Data Backup

Two directories need to be backed up:

- `/mnt/SSD/Containers/ocis/config` — `ocis.yaml` with all secrets and hashed passwords
- `/mnt/SSD/Containers/ocis/data` — all user files, metadata, and thumbnails

If you pre-set the three secrets in `.env` before the first run, you can recreate `ocis.yaml` from scratch by deleting it and restarting the container (it will re-run `ocis init`). Without pre-set secrets, losing the config volume means regenerating secrets and resetting the admin password.

## Upgrading

OCIS includes automatic data migrations on startup. To upgrade:

```bash
docker compose pull
docker compose up -d
docker compose logs -f ocis  # watch for migration output
```

Always back up both volumes before a major version upgrade.
