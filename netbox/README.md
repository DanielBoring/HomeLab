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
   [netbox]  ← Django/Granian on :8080
   /       \
[postgres] [redis]  [redis-cache]
            (tasks)    (page cache)
        │
[netbox-worker]   ← RQ worker for background jobs
```

Five containers total:

| Container | Image | Role |
|---|---|---|
| `netbox` | `netboxcommunity/netbox:v4.7.4-5.1.1` | Web UI + REST/GraphQL API |
| `netbox-worker` | `netboxcommunity/netbox:v4.7.4-5.1.1` | Background jobs (webhooks, scripts, reports) |
| `netbox-db` | `postgres:18.6-alpine` | Primary data store |
| `netbox-redis` | `redis:7-alpine` | Task queue (RQ) |
| `netbox-redis-cache` | `redis:7-alpine` | Django page cache |

The web app and RQ worker share an image and media/reports/scripts volumes.
No separate housekeeping container is configured in this stack.

---

## Prerequisites

This Compose file is for **fresh installations with empty database storage** or
an explicitly rehearsed PostgreSQL 16 migration. Never start PostgreSQL 18 on a
PostgreSQL 16 directory. Use [the migration procedure](#postgresql-16-to-18)
for existing data; changing a tag or moving files does not convert a cluster.

NetBox **v4.7.4 / NetBox-Docker 5.1.1** and PostgreSQL **18.6 Alpine** are
frozen by multi-platform digest in Compose. On 2026-10-31, the registry's
`latest` and `v4.7.4-5.1.1` NetBox tags resolved to the same content. This freezes
the current floating image; it does not identify any existing deployment.
The tagged upstream [5.1.1 stack](https://github.com/netbox-community/netbox-docker/blob/5.1.1/docker-compose.yml)
uses PostgreSQL 18 and mounts `/var/lib/postgresql`. The
[NetBox v4.7 release requirements](https://github.com/netbox-community/netbox/blob/v4.7.4/docs/release-notes/version-4.7.md)
specify PostgreSQL 15+ with `ltree`, and Redis 6+; this stack keeps Redis 7.
Existing deployments must already match the selected NetBox image, or complete
a separately reviewed application upgrade on PostgreSQL 16 first. Review plugin,
configuration, GraphQL and remote-image-storage changes for that application
upgrade; do not combine an unknown app upgrade with this database migration.

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

The retained `NETBOX_ADMIN_API_TOKEN` variable is legacy and does not create an
API token with this pinned image. Review modern token pepper/key configuration
separately before enabling API integrations; this stack does not supply it.

### 2. Create host directories

```bash
mkdir -p /mnt/SSD/Containers/netbox/{db,redis,redis-cache,media,reports,scripts}
```

### 3. Start the stack

```bash
docker compose up -d
```

NetBox checks database migrations on startup; a fresh database can take several
minutes to initialize. Watch progress with:

```bash
docker logs -f netbox
```

Wait for `docker compose ps` to report the web service healthy and check both
web and worker logs. The selected image uses Granian. An initialization message
alone does not prove HTTP readiness or that the worker executes jobs.

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
| `NETBOX_ADMIN_API_TOKEN` | No | Legacy variable; unused for token creation in this pinned stack |
| `NETBOX_DOMAIN` | Yes | Hostname Traefik routes to NetBox |
| `NETBOX_PORT` | No | Host port for direct access (default: `8060`) |

¹ **Bootstrap only.** The selected image creates the named superuser only if
that username does not exist; an existing username is left unchanged. Keep the
original admin name during migration to avoid creating another superuser. For
later password changes use the UI or
`docker compose exec netbox /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py changepassword <username>`.
The selected [bootstrap script](https://github.com/netbox-community/netbox-docker/blob/5.1.1/docker/super_user.py)
requires modern token pepper/key settings to create an API token; the legacy
40-hex token value alone does not do so.

---

## Upgrading

Update literal versions/digests only after reviewing the matching upstream
release, taking a complete restore set and rehearsing restore. Web and worker
must always use the same application image. With reviewed references in place,
`docker compose pull` fetches that content and `docker compose up -d` recreates
services. Startup can migrate the application schema automatically, so do not
start web or worker against an unrestored database.

### PostgreSQL 16 to 18

**Do not auto-deploy this onto existing data.** Pause Git polling/image updaters,
API clients, integrations, scheduled jobs and all other writers first. Drain
background queues before stopping workers. Rehearse on a separate, isolated
restore with outbound webhooks/integrations blocked, then schedule downtime.
The following examples are for one root Bash session on the Linux Docker host,
from the **currently deployed PostgreSQL 16** `netbox/` directory. They are
operational instructions to review, not commands to run simply to review a PR.

This procedure is only for this dedicated single-database stack, with database
and owner both `netbox`. Confirm actual roles, databases, extensions, tablespaces,
custom authentication/server settings and storage first. A single `pg_dump`
does not preserve cluster-wide roles or PostgreSQL configuration. Extra roles,
external databases, plugins, remote storage or custom tablespaces need a tailored
migration. Keep an independent backup off this host.

1. Verify Docker context, deployed PostgreSQL version and storage privately.
   Check that Compose uses the existing project name and all five containers
   belong to it. The preflight below rejects mounted datasets anywhere under
   the state tree. If TrueNAS uses a mounted ZFS dataset at any of these paths,
   stop and prepare a dataset-aware snapshot/clone and rollback procedure;
   do not rename a mounted dataset directory. Allow space for the dump and cold
   non-database archive plus a second database cluster.

   ```bash
   set -euo pipefail
   umask 077
   root=/mnt/SSD/Containers/netbox
   stamp=$(date -u +%Y%m%dT%H%M%SZ)
   backup="/root/netbox-pg18-$stamp"
   old_db_dir="/mnt/SSD/Containers/netbox-db.pg16-$stamp"
   test -d "$root/db"
   test ! -L "$root"
   for directory in db redis redis-cache media reports scripts; do
     test -d "$root/$directory"
     test ! -L "$root/$directory"
   done
   test ! -e "$backup"
   test ! -e "$old_db_dir"
   command -v findmnt >/dev/null
   mounted_paths=$(findmnt -rn -o TARGET)
   if printf '%s\n' "$mounted_paths" | awk -v p="$root" \
     '$0 == p || index($0, p "/") == 1 {found=1} END {exit !found}'; then
     echo 'Mounted state path: prepare dataset-aware migration first.' >&2
     exit 1
   fi
   mkdir "$backup"
   cp -a .env "$backup/settings.env"
   cp -a compose.yaml "$backup/compose.pg16.yaml"
   project=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' netbox-db)
   test -n "$project"
   for c in netbox netbox-worker netbox-redis netbox-redis-cache; do
     test "$project" = "$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "$c")"
   done
   version_num=$(docker compose -p "$project" exec -T postgres psql -U netbox -d netbox -Atc 'SHOW server_version_num;')
   test "$version_num" -ge 160000
   test "$version_num" -lt 170000
   reviewed_image=netboxcommunity/netbox:v4.7.4-5.1.1@sha256:69cd72d0b0e4928a90940a7011954aaa7060c75fddd8dc6cea2f19407bae45b1
   docker pull "$reviewed_image"
   reviewed_id=$(docker image inspect --format '{{.Id}}' "$reviewed_image")
   test "$(docker inspect --format '{{.Image}}' netbox)" = "$reviewed_id"
   test "$(docker inspect --format '{{.Image}}' netbox-worker)" = "$reviewed_id"
   printf 'services:\n' > "$backup/images.pg16.yaml"
   image_ids=()
   for pair in postgres:netbox-db redis:netbox-redis redis-cache:netbox-redis-cache netbox:netbox netbox-worker:netbox-worker; do
     service=${pair%%:*}; container=${pair#*:}
     image_id=$(docker inspect --format '{{.Image}}' "$container")
     image_ids+=("$image_id")
     printf '  %s:\n    image: %s\n' "$service" "$image_id" >> "$backup/images.pg16.yaml"
   done
   docker image save -o "$backup/images.tar" "${image_ids[@]}"
   printf '%s\n' "$project" > "$backup/project-name"
   printf '%s\n' "$old_db_dir" > "$backup/old-db-path"
   ```

   A failed image comparison is a stop gate: inventory and review the application
   upgrade separately on PostgreSQL 16. Do not bypass it by changing the expected
   ID. Save any additional deployed Compose overrides/configuration too; these
   examples assume only `compose.yaml` and `.env`.
   Confirm the original Redis image IDs remain selected during this database
   migration; if a local/moving tag now selects different content, preserve the
   recorded IDs in a deployment override. Redis upgrades need separate review.

2. Stop web and worker after draining queues, then dump the still-running 16
   database. Stop on any error. Archive listing checks format; a successful
   isolated restore plus application checks establishes recoverability.

   ```bash
   docker compose -p "$project" stop netbox-worker netbox
   docker compose -p "$project" exec -T postgres \
     pg_dump --format=custom -U netbox -d netbox > "$backup/netbox.dump"
   test -s "$backup/netbox.dump"
   docker compose -p "$project" exec -T postgres pg_restore --list \
     < "$backup/netbox.dump" > "$backup/dump-contents.txt"
   docker compose -p "$project" down         # Never add -v / --volumes
   tar --numeric-owner --exclude='./db' -cpf "$backup/state.pg16.tar" -C "$root" .
   mv "$root/db" "$old_db_dir"
   mkdir "$root/db"
   ```

   The cold archive preserves Redis state, media/images, reports, scripts and
   host configuration. Retain the original `NETBOX_SECRET_KEY`, credentials,
   any API token peppers/custom authentication settings and exact image IDs.
   Keep the original PostgreSQL 16 directory intact with numeric ownership.
   The new empty directory is initialized by PostgreSQL; do not copy 16 files
   into it or blanket-chown database storage to the app's user.

3. Replace the deployed Compose with this reviewed PostgreSQL 18 file, retaining
   the same `.env`, project name and custom mounts/settings. Start only the
   database and Redis services. Do not start web or worker until restore passes.

   ```bash
   docker compose -p "$project" config --quiet
   docker compose -p "$project" pull postgres netbox netbox-worker
   docker compose -p "$project" up -d postgres redis redis-cache
   # Wait for readiness; inspect logs if this fails.
   docker compose -p "$project" exec -T postgres pg_isready -U netbox -d netbox
   docker compose -p "$project" exec -T postgres \
     pg_restore --exit-on-error --single-transaction --no-owner -U netbox -d netbox \
     < "$backup/netbox.dump"
   docker compose -p "$project" exec -T postgres \
     psql -v ON_ERROR_STOP=1 -U netbox -d netbox \
       -c 'ANALYZE;' -c 'SHOW server_version;' -c 'SHOW data_directory;' \
       -c 'SELECT extname FROM pg_extension ORDER BY extname;'
   ```

   Confirm PostgreSQL 18, data directory `/var/lib/postgresql/18/docker`, and
   required extensions including `ltree`. The bind-backed named volume still
   points to host `db`, but now mounts the container parent `/var/lib/postgresql`.
   No password/key rotation is part of this move. Changing `POSTGRES_PASSWORD`
   initializes empty storage only; it does not rotate an existing role.

4. Keep clients and outbound integrations isolated. Start web, wait for health,
   then start worker; inspect both logs. Verify login with the existing account,
   permissions, representative sites/devices/IPs, media, API authentication and
   a harmless local background job. Confirm expected queues/schedules without
   firing real webhooks. Recreate PostgreSQL and recheck persistence. Resume
   access/integrations/updaters only after acceptance; retain backup and original
   16 storage for the agreed rollback window.

   ```bash
   docker compose -p "$project" up -d netbox netbox-worker
   docker compose -p "$project" ps
   docker compose -p "$project" logs --tail=100 netbox netbox-worker
   ```

**Rollback before normal writes resume:** stop the 18 stack and preserve its
state tree, restore cold files and the original 16 database, settings and image
IDs. Never point PostgreSQL 16 at the PostgreSQL 18 directory. In the same root
session, with `$backup`, `$project`, `$old_db_dir`, `$root` and `$stamp` intact:

```bash
docker compose -p "$project" down           # No -v
test ! -e "/mnt/SSD/Containers/netbox.pg18-failed-$stamp"
mv "$root" "/mnt/SSD/Containers/netbox.pg18-failed-$stamp"
mkdir "$root"
tar --numeric-owner -xpf "$backup/state.pg16.tar" -C "$root"
mv "$old_db_dir" "$root/db"
docker image load -i "$backup/images.tar"
docker compose -p "$project" --env-file "$backup/settings.env" \
  -f "$backup/compose.pg16.yaml" -f "$backup/images.pg16.yaml" \
  up -d --pull never postgres redis redis-cache
# Wait for readiness before starting web/worker.
docker compose -p "$project" --env-file "$backup/settings.env" \
  -f "$backup/compose.pg16.yaml" -f "$backup/images.pg16.yaml" \
  exec -T postgres pg_isready -U netbox -d netbox
docker compose -p "$project" --env-file "$backup/settings.env" \
  -f "$backup/compose.pg16.yaml" -f "$backup/images.pg16.yaml" \
  up -d --pull never netbox netbox-worker
```

Recheck login, records, media and worker operation. Restore the deployed Compose
and settings to their original versions before allowing Git polling to resume.
After normal writes resume on 18, the retained 16 directory is stale; restoring
it discards those writes. Stop and plan reconciliation instead.

The [official PostgreSQL image](https://hub.docker.com/_/postgres) documents the
18 parent mount and initialization behavior; PostgreSQL documents
[major-version dump/restore](https://www.postgresql.org/docs/18/upgrading.html).

---

## Initial configuration

Work through these in order — later steps (devices, IPs) depend on the organizational structure you set up first.

### 1. Create a regular user

The `admin` superuser should not be your day-to-day account. Create a normal user under Admin → Users with only the permissions you need. Reserve the superuser for schema changes and bulk operations.

### 2. Restrict anonymous access

The pinned release defaults to requiring login. Preserve this setting in custom
configuration. A single-file override can explicitly set it:

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
[selected 5.1.1 configuration loader](https://github.com/netbox-community/netbox-docker/blob/5.1.1/docker/configuration.docker.py).

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

NetBox exposes its object data through the REST API. API-token bootstrap is not
configured by this stack. Review the selected release's token settings and
preserve any existing token peppers before configuring authentication. Once a
working token is available, use its displayed Authorization header; the example
below is for an existing legacy token, not a modern v2 token:

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
