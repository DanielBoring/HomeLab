# NetBox

NetBox is an open-source IPAM (IP Address Management) and DCIM (Data Center Infrastructure Management) tool. If you've ever lost track of which IPs are assigned, forgotten what a switch port connects to, or needed a single source of truth for your network topology, NetBox is the answer. It models your infrastructure — IP prefixes, individual addresses, VLANs, devices, racks, cables — and exposes everything through a clean web UI and a full REST/GraphQL API.

**When it makes sense to run this:** Any homelab that has grown beyond a handful of devices benefits from a proper IPAM. If you're manually tracking IPs in a spreadsheet or relying on your router's DHCP leases table as a source of truth, NetBox is a meaningful upgrade. The API also makes it a useful data source for automation (Ansible, Terraform, custom scripts).

---

## Architecture

```
Browser / API client
        │
    [Traefik]  ← TLS termination, lan-only middleware
        │
   [netbox]  ← Django/gunicorn on :8080
   /       \
[postgres] [redis]  [redis-cache]
            (tasks)    (page cache)
        │
[netbox-worker]   ← RQ worker for background jobs
[netbox-housekeeping]  ← Daily cleanup cron (runs once/day)
```

Five containers total:

| Container | Image | Role |
|---|---|---|
| `netbox` | `netboxcommunity/netbox` | Web UI + REST/GraphQL API |
| `netbox-worker` | `netboxcommunity/netbox` | Background jobs (webhooks, scripts, reports) |
| `netbox-housekeeping` | `netboxcommunity/netbox` | Daily maintenance (clears stale sessions, old change records) |
| `netbox-db` | `postgres:16-alpine` | Primary data store |
| `netbox-redis` | `redis:7-alpine` | Task queue (RQ) |
| `netbox-redis-cache` | `redis:7-alpine` | Django page cache |

The worker and housekeeping containers share the same image as the main app — they just run different entry points (`manage.py rqworker` and `housekeeping.sh`). Volumes for media, reports, and scripts are shared across all three so uploaded files and custom scripts are available wherever the app runs them.

---

## Prerequisites

- `traefik` network already created (`docker network create traefik`)
- Host directories created before first `docker compose up`:

```bash
mkdir -p /mnt/SSD/Containers/netbox/{db,redis,redis-cache,media,reports,scripts}
```

---

## Deployment

### 1. Create the `.env` file

```bash
cp .env.example .env
```

Edit `.env` and fill in all values. For the secret key, generate a strong one:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(60))"
```

For the API token, generate a 40-character hex string:

```bash
python3 -c "import secrets; print(secrets.token_hex(20))"
```

### 2. Create host directories

```bash
mkdir -p /mnt/SSD/Containers/netbox/{db,redis,redis-cache,media,reports,scripts}
```

### 3. Start the stack

```bash
docker compose up -d
```

NetBox runs a database migration on every startup — the first boot takes 60–90 seconds. Watch progress with:

```bash
docker logs -f netbox
```

The app is ready when you see `Gunicorn is running`.

### 4. Access

- Via Traefik: `https://${NETBOX_DOMAIN}` (LAN only)
- Direct: `http://<host-ip>:8060`

Log in with the credentials from `NETBOX_ADMIN_USER` / `NETBOX_ADMIN_PASSWORD`.

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `TZ` | No | Timezone (default: `America/New_York`) |
| `NETBOX_DB_PASSWORD` | Yes | PostgreSQL password for the `netbox` user |
| `NETBOX_REDIS_PASSWORD` | Yes | Redis password for the task queue instance |
| `NETBOX_REDIS_CACHE_PASSWORD` | Yes | Redis password for the cache instance |
| `NETBOX_SECRET_KEY` | Yes | Django secret key — min 50 chars, never share or rotate without clearing sessions |
| `NETBOX_ADMIN_USER` | Yes¹ | Superuser username |
| `NETBOX_ADMIN_EMAIL` | Yes¹ | Superuser email |
| `NETBOX_ADMIN_PASSWORD` | Yes¹ | Superuser password |
| `NETBOX_ADMIN_API_TOKEN` | Yes¹ | Superuser API token — 40 hex chars |
| `NETBOX_DOMAIN` | Yes | Hostname Traefik routes to NetBox |
| `NETBOX_PORT` | No | Host port for direct access (default: `8060`) |

¹ **First-run only.** On startup, NetBox checks whether any superuser exists in the database. If none does, it creates one using these four vars. On every subsequent startup the check finds an existing superuser and skips the step — the vars are never read again. To change credentials after first run, use the web UI (profile → change password) or `docker exec -it netbox python manage.py changepassword <username>`.

---

## Upgrading

NetBox releases frequently. To upgrade:

```bash
docker compose pull
docker compose up -d
```

Migrations run automatically on startup. Check the release notes before upgrading across major versions.

---

## Useful things to configure after first login

1. **Set your home prefixes** — go to IPAM → Prefixes → Add. Start with your LAN (`10.0.0.0/20`).
2. **Enable login required** — by default NetBox allows anonymous read access. To require login for all views, create `/etc/netbox/config/extra.py` (mounted into the container) containing `LOGIN_REQUIRED = True`.
3. **Webhooks** — NetBox can POST change events to external URLs (Home Assistant, ntfy, etc.) via the netbox-worker. Configure under Integrations → Webhooks.
4. **Custom scripts & reports** — drop Python files into the `scripts/` or `reports/` directories (mapped to `/mnt/SSD/Containers/netbox/scripts|reports`) and they appear in the UI under Customization.
