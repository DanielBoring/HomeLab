# NetBox

NetBox is an open-source IPAM (IP Address Management) and DCIM (Data Center Infrastructure Management) tool. If you've ever lost track of which IPs are assigned, forgotten what a switch port connects to, or needed a single source of truth for your network topology, NetBox is the answer. It models your infrastructure — IP prefixes, individual addresses, VLANs, devices, racks, cables — and exposes everything through a clean web UI and a full REST/GraphQL API.

**When it makes sense to run this:** Any homelab that has grown beyond a handful of devices benefits from a proper IPAM. If you're manually tracking IPs in a spreadsheet or relying on your router's DHCP leases table as a source of truth, NetBox is a meaningful upgrade. The API also makes it a useful data source for automation (Ansible, Terraform, custom scripts).

---

## Architecture

```text
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
```

Five containers total:

| Container | Image | Role |
|---|---|---|
| `netbox` | `netboxcommunity/netbox` | Web UI + REST/GraphQL API |
| `netbox-worker` | `netboxcommunity/netbox` | Background jobs (webhooks, scripts, reports) |
| `netbox-db` | `postgres:16-alpine` | Primary data store |
| `netbox-redis` | `redis:7-alpine` | Task queue (RQ) |
| `netbox-redis-cache` | `redis:7-alpine` | Django page cache |

The web app and RQ worker share an image and media/reports/scripts volumes.
No separate housekeeping container is configured in this stack.

---

## Prerequisites

- Traefik deployed first to own/create the external `traefik` network
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

Back up the complete restore set below and review app/database migrations first.
These un-inventoried images need verified literal version/digest selection;
`pull` against moving tags is not a reviewed upgrade. After updating references:

```bash
docker compose pull
docker compose up -d
```

Migrations run automatically on startup. Check the release notes before upgrading across major versions.

---

## Initial configuration

Work through these in order — later steps (devices, IPs) depend on the organizational structure you set up first.

### 1. Create a regular user

The `admin` superuser should not be your day-to-day account. Create a normal user under Admin → Users with only the permissions you need. Reserve the superuser for schema changes and bulk operations.

### 2. Restrict anonymous access

By default NetBox allows unauthenticated read access to everything. To require login, mount a config file into the container and add one line:

```python
# /mnt/SSD/Containers/netbox/config/extra.py
LOGIN_REQUIRED = True
```

Create the host file first, then merge this **single-file** mount into the
existing volumes of both `netbox` and `netbox-worker`. Do not mount an empty host
directory over `/etc/netbox/config` and hide the image's required config:

```yaml
- type: bind
  source: /mnt/SSD/Containers/netbox/config/extra.py
  target: /etc/netbox/config/extra.py
  read_only: true
  bind:
    create_host_path: false
```

Validate the model and recreate both services to apply the new mount; a restart
does not change mounts. The separate override-file pattern is documented in
[netbox-docker 3.2.0 configuration](https://github.com/netbox-community/netbox-docker/blob/3.2.0/configuration/configuration.py)
(checked 2026-10-13); confirm the selected image's matching loader before use.

### 3. Create a Site

NetBox's organizational hierarchy starts with a **Site** — a physical location that racks, devices, and VLANs hang off.

Organization → Sites → Add:
- **Name:** `Home` (or whatever you call it)
- **Status:** Active
- **Physical address:** optional, useful for geo context

Everything else in NetBox will reference this site.

### 4. Set up IP space

NetBox models IP address space in three layers:

| Layer | What it is | Example |
|---|---|---|
| **Aggregate** | A top-level block you own/manage | `10.0.0.0/8` (RFC 1918) |
| **Prefix** | A subnet carved out of the aggregate | `10.0.0.0/20` (your LAN) |
| **IP Address** | A single assigned address | `10.0.1.1/20` (UDM SE) |

**Add the RFC 1918 aggregate** (IPAM → Aggregates → Add):
- Prefix: `10.0.0.0/8`
- RIR: create one called `RFC 1918` with `Private` checked

**Add your prefixes** (IPAM → Prefixes → Add):

| Prefix | Site | Role | Description |
|---|---|---|---|
| `10.0.0.0/20` | Home | LAN | Main LAN |
| `10.0.5.0/24` | Home | Infrastructure | Traefik macvlan subnet |

NetBox will warn you if you try to assign an IP outside a known prefix, which catches typos and subnet mistakes early.

### 5. Add VLANs

If your network is segmented, model it now so you can attach VLANs to prefixes and device interfaces later.

IPAM → VLANs → Add one per segment. Set the Site to `Home` so they're scoped correctly.

### 6. Add device types

Device types are the template (manufacturer + model) that individual devices are instances of. You only define a device type once and then stamp out as many devices as you own.

Organization → Manufacturers → Add each vendor (`Ubiquiti`, `45Drives`, etc.).

Organization → Device Types → Add:
- **Manufacturer:** Ubiquiti
- **Model:** UDM-SE
- **Form factor:** 1U (or Desktop)

The NetBox community maintains a library of pre-built device type definitions at [github.com/netbox-community/devicetype-library](https://github.com/netbox-community/devicetype-library) — worth importing rather than building from scratch.

### 7. Add devices and assign IPs

Organization → Devices → Add a device for each piece of physical hardware. Attach it to a device type, site, and (optionally) rack/location.

Once a device exists, open it → Interfaces tab → add the management interface → then assign an IP address from your prefix. Marking one IP as the **primary** makes it show in device list views and enables future integration with Ansible inventory plugins.

Start with the core infrastructure:
- UDM SE (`10.0.1.1`)
- TrueNAS host
- Proxmox nodes
- Switches and APs

### 8. Document services as Virtual Machines or services

For Docker workloads, model them as **Virtual Machines** under Virtualization (or skip this and just use IPAM to track the IPs — your call on how granular you want to go).

### 9. Use the API

Every action you took in the UI is available via REST API. Your API token (set during first run) authenticates requests. Quick test:

```bash
curl -s -H "Authorization: Token <your-token>" \
  https://netbox.virtuallyboring.com/api/ipam/prefixes/ | jq '.results[].prefix'
```

The interactive API docs are at `https://netbox.virtuallyboring.com/api/docs/` — every endpoint is documented with request/response examples.

### 10. Webhooks and automation

NetBox can POST a JSON payload to any URL when objects are created, updated, or deleted. Practical homelab uses:
- Trigger an Ansible playbook via Semaphore when a device is added
- Send a notification to ntfy/Slack on IP assignment
- Keep an external DNS provider in sync

Configure under Integrations → Event Rules.

## Recovery and operational safeguards

Run Linux/Bash examples from `netbox/`. Restrict direct host port 8060 separately
from Traefik. Preserve DB/Redis image-specific ownership; give the app user
appropriate media/reports/scripts access rather than blanket-chowning the tree.
Check all five services/logs plus authenticated API/UI access and worker status.
Readiness logs alone do not verify jobs.

Pause clients and background automation, stop all writers, and preserve the
whole NetBox tree (`db`, both Redis paths, `media`, `reports`, `scripts` and any
host config), original `NETBOX_SECRET_KEY`, private settings and image versions.
Use the [shared recovery procedure](../README.md#backing-up-data). Restore to
empty compatible storage with original owners, start databases/cache before the
app, and keep workers/webhooks isolated until records, uploads and login pass.
Changing initialization password variables does not rotate existing DB roles.
