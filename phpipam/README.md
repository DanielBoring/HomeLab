# phpIPAM

[phpIPAM](https://phpipam.net) is an open-source IP address management (IPAM) tool. It tracks subnet allocations, individual IP assignments, VLANs, VRFs, and devices — giving you a searchable source of truth for your network addressing instead of a spreadsheet.

Run it when your homelab has grown to the point where you're guessing whether an IP is in use, or when you want to plan subnets before assigning them. It's lighter-weight than NetBox and purpose-built for IP management specifically.

## Architecture

```
Browser → Traefik (TLS + lan-only) → phpipam-web :80
                                           ↓
                                      phpipam-db (MariaDB)
                                           ↑
                                      phpipam-cron (network scanning)
```

Three containers:
- **phpipam-web** — Apache/PHP frontend
- **phpipam-db** — MariaDB 11 database
- **phpipam-cron** — runs scheduled network discovery scans (ping sweeps, SNMP)

The web and cron containers require `NET_ADMIN` and `NET_RAW` capabilities for ping and SNMP to work. The cron container stays on the internal `phpipam` network; only the web container joins `traefik`.

## Prerequisites

- Traefik running with the `traefik` external network created
- Host directories created:

```bash
sudo mkdir -p /mnt/SSD/Containers/phpipam/{db,logo,ca}
```

## Deployment

### 1. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

| Variable | Description |
|---|---|
| `TZ` | Timezone (default: `America/New_York`) |
| `PHPIPAM_DOMAIN` | FQDN Traefik routes to phpIPAM (e.g. `ipam.virtuallyboring.com`) |
| `PHPIPAM_PORT` | Host port for direct access (default: `8030`) |
| `PHPIPAM_DB_PASSWORD` | MariaDB password for the `phpipam` user |
| `PHPIPAM_DB_ROOT_PASSWORD` | MariaDB root password |

### 2. Start

```bash
docker compose up -d
docker compose logs -f phpipam-web
```

MariaDB will initialize on first start — wait for the healthcheck to pass before the web container comes up.

### 3. Access

- **Via Traefik:** `https://<PHPIPAM_DOMAIN>` (LAN only)
- **Direct:** `http://<host-ip>:8030`

## Initial Configuration

### 1. Run the installer

On first visit, phpIPAM detects no database schema and redirects to the installer at `/install/`. Choose **Automatic database installation**.

It will prompt for database credentials — these are the **root** credentials phpIPAM needs to create the schema, not the application user:

| Field | Value |
|---|---|
| Username | `root` |
| Password | `PHPIPAM_DB_ROOT_PASSWORD` from your `.env` |
| Database location | `phpipam-db` (Docker DNS hostname of the MariaDB container) |

After this one-time step, phpIPAM switches to the `phpipam` user for all normal operation.

### 2. Log in

Default credentials after install:

| Field | Value |
|---|---|
| Username | `admin` |
| Password | `ipamadmin` |

**Change the admin password immediately** via *Administration → Users → admin → Change password*.

### 3. Configure your site settings

Go to *Administration → phpIPAM settings*:

- Set **Site URL** to your `PHPIPAM_DOMAIN` — required for correct redirect and link generation behind a reverse proxy
- Enable modules you want in the sidebar (Subnets, Hosts, VLANs, VRFs, etc.)
- Set your preferred **IP addressing format** (IPv4 / dual-stack)

### 4. Add your subnets

Go to *Subnets* → select or create a **Section** (e.g. "HomeLab") → *Add subnet*:

- Enter the network in CIDR notation (e.g. `10.0.0.0/20`)
- Enable **Check hosts** if you want the cron job to ping-sweep and auto-mark IPs as used/free
- Optionally enable **DNS resolution** to auto-resolve hostnames

### 5. Configure network discovery (optional)

The `phpipam-cron` container runs scans on the interval set by `SCAN_INTERVAL` (default: `1h`). For subnets to be scanned, discovery must be enabled on each subnet individually under *Subnet → Edit → Discovery*.

For SNMP discovery, add your devices under *Devices* and configure community strings in *Administration → SNMP communities*.

## Updating

```bash
docker compose pull
docker compose up -d
```
