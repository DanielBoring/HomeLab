# Unbound

A validating, recursive, caching DNS resolver. Unbound resolves DNS queries by walking the DNS tree from the root servers down to the authoritative nameserver for each domain — no third-party DNS provider ever sees your queries.

Used in this homelab as the upstream recursive resolver for Pi-hole, replacing the default forwarders (8.8.8.8, 1.1.1.1) with a fully self-hosted DNS chain.

## Why run a recursive resolver?

When Pi-hole forwards queries to 8.8.8.8 or 1.1.1.1, Google or Cloudflare sees every domain you look up. Unbound eliminates that:

- Queries go directly to authoritative DNS servers — no intermediary
- DNSSEC validation is performed locally, not trusted to a third party
- Reduces DNS round-trip time for frequently-queried domains (cache is local)

## Architecture

```
Client device
     │
     ▼  port 53
  Pi-hole          ← blocks ads/trackers, caches, logs queries
     │
     ▼  port 5335 (host) or port 53 (Docker dns network)
   Unbound         ← recursive resolver, DNSSEC validation
     │
     ▼  port 53
Root DNS servers → TLD servers → Authoritative servers
```

## Overview

| Setting | Value |
|---|---|
| Image | `mvance/unbound:latest` |
| Access | DNS only — no web UI |
| Host port | `${UNBOUND_PORT:-5335}` (UDP + TCP) |
| Config | `/mnt/SSD/Containers/unbound` |
| Docker network | `dns` (bridge, created by this compose) |

> Port 5335 is the convention from the official Pi-hole + Unbound guide. It avoids conflict with `systemd-resolved` which holds port 53 on most Linux hosts.

## Prerequisites

Create the config directory before deploying:

```bash
mkdir -p /mnt/SSD/Containers/unbound
```

> `mvance/unbound` runs as the `unbound` user internally — no `chown` needed.

## Quick Start

### 1. Copy the environment template

```bash
cp example.env .env
```

### 2. Edit .env if needed

| Variable | Default | Description |
|---|---|---|
| `UNBOUND_PORT` | `5335` | Host port Unbound listens on |

The defaults work without changes unless port 5335 is already in use.

### 3. Deploy

```bash
docker compose up -d
```

### 4. Verify

Query Unbound directly to confirm it's resolving:

```bash
dig cloudflare.com @<host-ip> -p 5335
```

Expected: a valid `A` record response with `status: NOERROR`.

Test DNSSEC validation (this should return `SERVFAIL` — that's correct):

```bash
dig sigfail.verteiltesysteme.net @<host-ip> -p 5335
```

A `SERVFAIL` response confirms Unbound is actively rejecting DNSSEC-invalid records.

## Pi-hole Integration

Unbound replaces Pi-hole's upstream DNS. Two methods depending on how Pi-hole is deployed.

### Method A — Docker (recommended)

If Pi-hole runs as a Docker container, join it to the `dns` network so it can reach Unbound by container name without exposing a host port.

In Pi-hole's `compose.yaml`:

```yaml
services:
  pihole:
    # ... existing config ...
    networks:
      - pihole        # Pi-hole's own network (whatever you have)
      - dns           # shared with Unbound

networks:
  pihole:
    driver: bridge
  dns:
    external: true    # created and owned by unbound/compose.yaml
```

Then in Pi-hole's settings, set the upstream DNS server to:

```
Custom 1: unbound#53
```

Use the container name `unbound` — Docker's internal DNS resolves it to the right IP on the shared `dns` network.

> **Deploy order:** Unbound must be running before Pi-hole starts, because Pi-hole
> tries to reach its upstream DNS at launch. Run `docker compose up -d` in
> `unbound/` first, then `pihole/`.

### Method B — Host port (non-Docker Pi-hole or TrueNAS native app)

If Pi-hole is running as a TrueNAS Scale app or on a separate host, use the host port instead:

In Pi-hole's DNS settings, set the upstream DNS server to:

```
Custom 1: <truenas-ip>#5335
```

Replace `<truenas-ip>` with the IP address of your TrueNAS host (e.g. `10.0.1.50`).

> Do not use `127.0.0.1` here — Pi-hole's container has its own loopback and
> cannot reach Unbound that way.

### Disabling Pi-hole's default upstreams

After configuring Unbound, remove all other upstream DNS servers in Pi-hole's settings (Cloudflare, Google, etc.). Leaving them enabled means some queries bypass Unbound entirely.

In Pi-hole → Settings → DNS:
- Uncheck all preset upstream servers
- Set only your Unbound address under "Custom DNS"

## Configuration

`mvance/unbound` ships with a well-tuned default configuration that handles:

- DNSSEC validation with auto-updated root hints
- Negative TTL caching (reduces repeated failed lookups)
- Prefetching (refreshes popular cache entries before they expire)
- Hardened security defaults (QNAME minimisation, refuse ANY queries)

### Customising

To override or extend the configuration, add `.conf` files to the mounted volume directory. Unbound includes all `.conf` files from `/opt/unbound/etc/unbound/`:

```bash
# On the TrueNAS host
nano /mnt/SSD/Containers/unbound/custom.conf
```

Example: add a local DNS override so a hostname resolves to a specific IP

```conf
server:
    local-data: "nas.home.arpa. A 10.0.1.50"
    local-data-ptr: "10.0.1.50 nas.home.arpa."
```

Restart Unbound after any config change:

```bash
docker compose restart unbound
```

### Private reverse DNS (RFC 1918)

Unbound's default config refuses recursive lookups for RFC 1918 addresses (10.x, 192.168.x, 172.16-31.x) because those zones have no authoritative DNS on the public internet. This means reverse lookups for LAN IPs return `NXDOMAIN`.

To serve your own reverse DNS, add a local zone:

```conf
server:
    local-zone: "0.10.in-addr.arpa." static
    local-data-ptr: "10.0.1.1   router.home.arpa."
    local-data-ptr: "10.0.1.50  nas.home.arpa."
```

## Storage

| Data | Path |
|---|---|
| Unbound config + root hints | `/mnt/SSD/Containers/unbound` |

## Maintenance

### Update image

```bash
docker compose pull
docker compose up -d
```

### View logs

```bash
docker compose logs -f unbound
```

### Check health

```bash
docker inspect --format='{{.State.Health.Status}}' unbound
```

### Backup

Config is just files — back up the bind-mounted directory:

```bash
tar -czf unbound-backup-$(date +%Y%m%d).tar.gz /mnt/SSD/Containers/unbound
```

## Troubleshooting

**Queries time out**

Check that Unbound can reach the internet. It needs outbound UDP/TCP port 53 to query root and authoritative servers. If your firewall blocks outbound DNS, Unbound cannot resolve anything.

**Pi-hole shows "upstream timeout" errors**

Confirm the upstream address in Pi-hole matches the container name (`unbound`) or host IP + port. Check that both containers are on the `dns` network: `docker network inspect dns`.

**DNSSEC failures for legitimate domains**

Some ISPs or corporate firewalls tamper with DNS responses in ways that break DNSSEC. If you're seeing widespread SERVFAIL for domains that should resolve, check whether Unbound is behind a filtering firewall. You can temporarily disable DNSSEC validation in `custom.conf` with `val-permissive-mode: yes` to test.

**`dig` returns old cached answers**

Unbound caches aggressively. Force a fresh lookup with:

```bash
dig +nocache cloudflare.com @<host-ip> -p 5335
```
