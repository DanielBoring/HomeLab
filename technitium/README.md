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
