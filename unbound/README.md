# Unbound

A validating, recursive, caching DNS resolver. With the committed
[`unbound.conf`](unbound.conf) installed on the host, queries go to root and
authoritative servers rather than an upstream forwarding provider. Recursion is
not encrypted DNS or anonymity: authoritative servers and network observers can
still see traffic.

Used in this homelab as the upstream recursive resolver for Pi-hole, replacing the default forwarders (8.8.8.8, 1.1.1.1) with a fully self-hosted DNS chain.

Images in `compose.yaml` are frozen to the inventoried builds. See the [image update guide](../README.md#image-updates); `docker compose pull` alone does not upgrade them.

## Why run a recursive resolver?

The image's generated defaults forward to Cloudflare; installing the explicit
configuration below is essential to the intended recursive behavior:
Compose refuses startup when the host configuration is missing instead of
silently generating the image's forwarding defaults. It does not rewrite an
existing config; review/install the selected file before redeployment.

- Queries go directly to authoritative DNS servers — no intermediary
- DNSSEC validation is performed locally, not trusted to a third party
- Reduces DNS round-trip time for frequently-queried domains (cache is local)

## Architecture

```text
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
| Image | `mvance/unbound`, digest-pinned in [compose.yaml](compose.yaml) |
| Access | DNS only — no web UI |
| Host port | `${UNBOUND_PORT:-5335}` (UDP + TCP) |
| Config | `/mnt/SSD/Containers/unbound` |
| Docker network | `<project>_dns` (owned bridge; normally `unbound_dns` with project `unbound`) |

> The default host port 5335 avoids using host port 53. Check actual listeners
> rather than assuming which DNS service runs on TrueNAS. Restrict UDP/TCP DNS
> access to trusted clients; do not expose an open resolver.

## Prerequisites

Run Bash commands on the Linux host from `unbound/`. For a **new installation**:

```bash
mkdir -p /mnt/SSD/Containers/unbound
install -m 644 unbound.conf /mnt/SSD/Containers/unbound/unbound.conf
```

The image starts as root to prepare its chroot devices and trust-anchor directory,
then Unbound drops privileges to `_unbound`; do not guess a fixed UID or force
`3001:3001`. Its entrypoint prepares `var/root.key` ownership.

For an **existing installation**, preserve its config and dataset snapshot first,
compare/merge local zones and access rules into the reviewed file, and plan DNS
downtime before replacing the host `unbound.conf`. An already-generated config is
not overwritten automatically by the entrypoint. This change intentionally
replaces forwarding with recursion: allow outbound UDP/TCP 53 and keep a
documented working DNS fallback for clients until validation succeeds.

## Quick Start

### 1. Copy the environment template

```bash
cp .env.example .env
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

Check an independently valid signed name with `dig +dnssec` for a successful
validated answer (`ad` flag), then the intentionally invalid name for `SERVFAIL`.
`SERVFAIL` alone does not prove DNSSEC works: network failures can cause it too.

## Pi-hole Integration

Unbound replaces Pi-hole's upstream DNS. Two methods depending on how Pi-hole is deployed.

### Method A — Docker (recommended)

If Pi-hole runs as a Docker container, join the actual Unbound project network.
The example assumes project name `unbound`, which creates `unbound_dns`. If
Portainer uses another stack/project name, replace `name:` with that deployed
network's name; verify it before starting Pi-hole.

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
    name: unbound_dns
```

Then in Pi-hole's settings, set the upstream DNS server to:

```text
Custom 1: unbound#53
```

Use `unbound` — Docker DNS resolves it on the shared network. Pi-hole is not
included in this public repository; this is an integration example, not an
already-deployed dependency.

> **Deploy order:** Unbound must be running before Pi-hole starts, because Pi-hole
> tries to reach its upstream DNS at launch. Run `docker compose up -d` in
> `unbound/` first, then `pihole/`.

### Method B — Host port (non-Docker Pi-hole or TrueNAS native app)

If Pi-hole is running as a TrueNAS Scale app or on a separate host, use the host port instead:

In Pi-hole's DNS settings, set the upstream DNS server to:

```text
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

The committed configuration uses the validator/iterator modules, built-in root
hints, managed DNSSEC trust anchor, QNAME minimisation and prefetch. It has **no**
`forward-zone` or `stub-zone`. IPv6 DNS transport is disabled for this IPv4 stack.
Recursion is allowed for loopback, the HomeLab `10.0.0.0/20` LAN and Docker
`172.16.0.0/12` bridges; adjust deliberately if your actual Docker subnet differs.

### Customising

Edit the host `unbound.conf` deliberately; arbitrary `.conf` files are **not**
automatically included. Add local directives under its existing `server:`
section (or add an explicit `include:` for a reviewed separate file):

```bash
# On the TrueNAS host
nano /mnt/SSD/Containers/unbound/unbound.conf
```

Example: add a local DNS override so a hostname resolves to a specific IP

```conf
server:
    local-data: "nas.home.arpa. A 10.0.1.50"
    local-data-ptr: "10.0.1.50 nas.home.arpa."
```

Check syntax before applying a planned config change, then restart during the
approved DNS window:

```bash
docker compose exec unbound unbound-checkconf /opt/unbound/etc/unbound/unbound.conf
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

Preserve the whole config directory, trust-anchor state and original
Compose/settings using the [shared backup procedure](../README.md#backing-up-data).
Coordinate a client DNS fallback during downtime. Restore to a fresh destination
with original ownership/version, check configuration and DNSSEC before repointing
clients. Do not delete a working config to test a replacement.

## Troubleshooting

**Queries time out**

Check that Unbound can reach the internet. It needs outbound UDP/TCP port 53 to query root and authoritative servers. If your firewall blocks outbound DNS, Unbound cannot resolve anything.

**Pi-hole shows "upstream timeout" errors**

Confirm the upstream address in Pi-hole matches the container name (`unbound`) or host IP + port. Check that both containers are on the actual project network, normally
`unbound_dns`: `docker network inspect unbound_dns`.

**DNSSEC failures for legitimate domains**

Check the host clock, root trust anchor, logs and outbound UDP/TCP 53 before
changing validation. Do not disable DNSSEC globally as routine troubleshooting.

**`dig` returns old cached answers**

`dig` has no `+nocache` option. A repeated query tests the resolver's current
answer, not a guaranteed fresh authoritative lookup:

```bash
dig cloudflare.com @<host-ip> -p 5335
```

Wait for the record TTL or use an intentionally uncached test name; do not
restart all client DNS just to bypass cache.

Configuration options were reviewed against
[NLnet Labs' reference](https://unbound.docs.nlnetlabs.nl/en/latest/manpages/unbound.conf.html)
and the [image entrypoint](https://github.com/MatthewVance/unbound-docker/blob/master/1.22.0/data/unbound.sh)
on 2026-10-13. No local Unbound binary or live recursive-resolution drill was
run; verify with `unbound-checkconf`, valid DNS replies and an intentionally
DNSSEC-invalid query before using this configuration as clients' sole resolver.
