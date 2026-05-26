# Technitium DNS Server

## What it is

Technitium DNS Server is a self-hosted, authoritative and recursive DNS server with a full web-based admin UI. It replaces the Pi-hole + Unbound combination with a single service that handles:

- **Recursive resolution** — queries upstream resolvers (DoH/DoT/UDP) directly, no separate Unbound needed
- **Ad/tracker blocking** — built-in blocklist support similar to Pi-hole
- **Local DNS zones** — create A/CNAME records for internal hostnames
- **DNS-over-HTTPS (DoH) / DNS-over-TLS (DoT)** — encrypted DNS endpoints for clients
- **Query logging & statistics** — per-client query history and dashboards

## Why use it instead of Pi-hole + Unbound

Pi-hole handles blocking and Pi-hole forwards to Unbound for recursion — two processes that need to stay in sync. Technitium does both in a single container with one config UI, making it simpler to manage, back up, and update.

## Architecture

```
LAN clients (port 53)
        |
  [Technitium :53]  <-- Docker, host-port bound
        |
   local zones?  yes → serve from local zone DB
        |
   blocklist hit? yes → NXDOMAIN / 0.0.0.0
        |
   upstream resolvers (Cloudflare DoH, Quad9, etc.)
        |
  Web admin UI (:5380) → Traefik → ${TECHNITIUM_DOMAIN}
```

The container is on the `traefik` network so the web UI is proxied by Traefik. DNS itself is published directly to host port 53 (UDP + TCP) — no Traefik involvement for DNS traffic.

## Host prerequisites

1. **Nothing else on port 53** — TrueNAS SCALE may have `systemd-resolved` using port 53. Check with `ss -tulnp | grep ':53'`. If it is active, disable it:
   ```bash
   systemctl stop systemd-resolved
   systemctl disable systemd-resolved
   ```
2. **Create bind-mount directories** before starting the container:
   ```bash
   mkdir -p /mnt/SSD/Containers/technitium/config
   mkdir -p /mnt/SSD/Containers/technitium/logs
   ```

## Quick start

```bash
cp example.env .env
# edit .env — set TECHNITIUM_ADMIN_PASSWORD and TECHNITIUM_DOMAIN
docker compose up -d
```

Open `https://${TECHNITIUM_DOMAIN}` (once DNS and Traefik are wired) or `http://<host-ip>:5380` on first boot (web UI is not behind Traefik until Traefik is resolving your domain).

Default admin username: `admin`

## Initial configuration

After `docker compose up -d`, open the web UI at `http://<host-ip>:5380` and log in with username `admin` and the password you set in `.env`.

### 1. General settings (Settings → General)

| Setting | Recommended value | Why |
|---|---|---|
| DNS Server Domain | `dns.virtuallyboring.com` | Pre-filled from `DNS_SERVER_DOMAIN` env var |
| Prefer IPv6 | Off | Avoids latency on single-stack LAN |
| QNAME Minimisation | On | Privacy — sends less query data to upstream |
| NSID | Off | Not needed for a private resolver |
| Log queries | On | Essential for debugging and stats |
| Log using local time | On | Matches your server's TZ |

### 2. Recursion (Settings → General → Recursion)

Set **Recursion** to `Allow Only For Private Networks`. This prevents your resolver from being used as an open recursive resolver if port 53 is ever accidentally reachable from the internet.

> If you need recursion for all clients unconditionally (e.g. split-horizon VPN), change this to `Allow` and tighten at the firewall level instead.

### 3. Forwarders (Settings → Forwarders)

Technitium can recurse fully on its own (like Unbound) or forward to upstream resolvers. For a homelab, forwarding to encrypted upstreams is simpler and faster:

1. Go to **Settings → Forwarders**
2. Enable **Quick Forwarding** (uses the fastest responding upstream)
3. Add upstreams — recommended set:

| Address | Protocol | Provider |
|---|---|---|
| `https://cloudflare-dns.com/dns-query` | HTTPS (DoH) | Cloudflare |
| `https://dns.quad9.net/dns-query` | HTTPS (DoH) | Quad9 (malware-blocking) |

4. Set **Forwarder Protocol** to `Https`
5. Enable **Fail on SERVFAIL** — drops an upstream if it returns errors

> To do full recursion instead (no forwarders, like Unbound), leave the forwarders list empty and set **Recursion** to `Allow Only For Private Networks`.

### 4. Blocking (Settings → Blocking)

1. Enable **Block List**
2. Add block list URLs. Recommended starting set:

| URL | List |
|---|---|
| `https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts` | StevenBlack (ads + malware) |
| `https://raw.githubusercontent.com/hagezi/dns-blocklists/main/domains/pro.txt` | Hagezi Pro |
| `https://raw.githubusercontent.com/hagezi/dns-blocklists/main/domains/tif.txt` | Hagezi Threat Intelligence |

3. Set **Blocking Type** to `NxDomain` (most compatible) or `Unspecified` (returns 0.0.0.0/:: which breaks some apps less)
4. Click **Save** then **Update Now** to pull all lists immediately

### 5. Local zone for internal hostnames (Zones → Add Zone)

To serve internal A/CNAME records (replacing Pi-hole's Local DNS):

1. **Zones → Add Zone**
2. Type: `Primary Zone`, name: your internal domain (e.g. `virtuallyboring.com` or `home.arpa`)
3. Add records:
   - Type `A` → hostname → LAN IP
   - Type `CNAME` → alias → target A record
4. No TTL changes needed for a homelab (default 3600 is fine)

### 6. Conditional forwarder (domain-specific routing)

A conditional forwarder sends queries for a specific domain to a designated DNS server instead of going through your normal forwarders or recursion. Use cases:

- Route `corp.example.com` queries to a corporate DNS server over VPN
- Route `home.arpa` or a split-horizon domain to a secondary internal resolver
- Forward `lan` or `.local` to a router/NAS that serves DHCP hostnames

**Steps:**

1. **Zones → Add Zone**
2. **Type:** `Conditional Forwarder Zone`
3. **Zone Name:** the domain to intercept (e.g. `corp.example.com`, `home.arpa`, or `lan`)
4. **Forwarder Protocol:** choose `Udp` for a LAN DNS server, `Https` for a corporate DoH endpoint
5. **Forwarder:** enter the IP or DoH URL of the target DNS server (e.g. `10.0.1.1` for your UDM SE, or `192.168.1.1` for a corporate gateway)
6. Click **Add**

> The zone name must be an exact suffix match — a zone for `corp.example.com` catches `host.corp.example.com` but not `example.com`. For a catch-all (forward everything, no local recursion), create a conditional forwarder zone for `.` (the root).

**Example — route `.home.arpa` to the UDM SE:**

| Field | Value |
|---|---|
| Zone Name | `home.arpa` |
| Forwarder | `10.0.1.1` |
| Protocol | `Udp` |

This means reverse-DNS queries for RFC 1918 addresses handed out by UniFi DHCP resolve to actual hostnames.

## Migrating from Pi-hole + Unbound

1. **Export Pi-hole custom DNS entries** (Settings → Local DNS → DNS Records) and recreate them as A/CNAME records under a local zone in Technitium.
2. **Export Pi-hole blocklists** (Group Management → Adlists) and add them under Settings → Blocking in Technitium.
3. **Point your router's DHCP DNS** to the TrueNAS host IP once Technitium is confirmed working.
4. Shut down the Proxmox Pi-hole and Unbound LXCs after a validation period.

## Environment variables

| Variable | Default | Required | Description |
|---|---|---|---|
| `TZ` | `America/New_York` | no | Container timezone |
| `TECHNITIUM_DOMAIN` | — | yes | Web UI domain; also sets the server's SOA hostname |
| `TECHNITIUM_ADMIN_PASSWORD` | — | yes | Admin panel password (set before first boot) |

Additional Technitium-specific env vars (all optional — configure via web UI instead):

| Variable | Description |
|---|---|
| `DNS_SERVER_RECURSION` | `Allow` / `AllowOnlyForPrivateNetworks` / `Deny` |
| `DNS_SERVER_FORWARDERS` | Comma-separated upstream IPs/DoH URLs |
| `DNS_SERVER_FORWARDER_PROTOCOL` | `Udp`, `Tcp`, `Tls`, `Https`, `HttpsJson` |

Full variable reference: <https://github.com/TechnitiumSoftware/DnsServer#environment-variables>

## Ports

| Port | Protocol | Purpose |
|---|---|---|
| 53 | UDP + TCP | DNS queries from LAN clients (host-bound) |
| 5380 | TCP | Web admin UI (internal, proxied by Traefik) |
