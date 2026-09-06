# Bambu Buddy on TrueNAS (Portainer)

Bambu Buddy is a self-hosted, local-network command center for Bambu Lab
printers. This stack exposes only its web UI through the existing LAN-only
Traefik route; it does not publish any TrueNAS host ports.

## Networking decision

This is deliberately a **bridge-networked Traefik deployment**, not the
upstream host-networking example. It provides a normal HTTPS route through the
shared `traefik` Docker network, protected by the existing
`secure-headers@file` and `lan-only@file` middlewares.

The trade-off is that Bambu Buddy cannot receive the multicast traffic needed
for automatic printer discovery. Add the printer manually using its reserved
LAN IP address. Create a DHCP reservation in UniFi first; do not use a
guest/isolated VLAN because the TrueNAS host must be able to reach the printer.

```
Browser on LAN
    |
    v HTTPS
Traefik (10.0.5.5)
    |
    v shared Docker bridge network
Bambu Buddy (port 8000, no host port)
    |
    v outbound LAN connections
Bambu printer (manual, DHCP-reserved IP)
```

## What this stack does

- Routes `https://bambuddy.virtuallyboring.com` through Traefik with TLS and
  the existing LAN-only allowlist.
- Does **not** publish port `8000`, so the web UI is not directly reachable on
  the TrueNAS host IP.
- Persists Bambu Buddy's SQLite database, archived print files, thumbnails,
  encryption key file, and logs under `/mnt/SSD/Containers/bambuddy/`.
- Pins the image to `v1.2.5.3`, a reviewed stable release. Upgrade deliberately
  through Portainer after reviewing upstream release notes.
- Keeps the optional virtual-printer capability available with
  `NET_BIND_SERVICE`; it does not expose the optional virtual-printer ports.

## Prerequisites

- The existing Traefik stack is running and has created the external
  `traefik` Docker network.
- A LAN DNS record for `bambuddy.virtuallyboring.com` points to Traefik's
  dedicated IP (`10.0.5.5`).
- The Bambu printer has a DHCP reservation and is reachable from the TrueNAS
  Docker host on the same trusted LAN/VLAN.
- Bambu Lab's LAN mode is enabled and its access code is available. Treat that
  access code as a secret; enter it in Bambu Buddy's web UI, never in this
  repository or Portainer's non-secret stack variables.

Create the persistent directories before the first deployment:

```sh
mkdir -p /mnt/SSD/Containers/bambuddy/data
mkdir -p /mnt/SSD/Containers/bambuddy/logs
chown -R 3001:3001 /mnt/SSD/Containers/bambuddy
```

## Configure

1. Copy `.env.example` to `.env` for command-line Compose use, or add its
   values as Portainer stack environment variables. Do not commit `.env`.
2. Generate a unique MFA encryption key and replace the placeholder:

   ```sh
   python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

   Keep this value for the lifetime of the deployment. Changing or losing it
   can make previously stored MFA secrets unreadable.
3. Confirm `BAMBUDDY_DOMAIN` matches the LAN DNS name and that
   `BAMBUDDY_VERSION` is a reviewed stable release.

## Portainer deployment

This repository only prepares the stack; it does not deploy it.

In Portainer, select the `TrueNAS.virtuallyboring.com` environment and create
a Git repository stack with Compose path `bambuddy/compose.yaml`. Supply the
environment variables from `.env.example` as stack variables, using the real
encryption key only in Portainer's protected configuration. Deploy only after
the DNS record, Traefik network, host paths, and DHCP reservation are ready.

After deployment:

1. Open `https://bambuddy.virtuallyboring.com` from a LAN client.
2. Complete Bambu Buddy's first-run setup and enable its own authentication.
   The Traefik IP allowlist is network access control, not a replacement for
   application authentication.
3. Add the printer manually using its DHCP-reserved IP, LAN access code, and
   serial number as prompted. Do not rely on automatic discovery in this
   topology.
4. Confirm the container becomes healthy and test a read-only status/camera
   view before enabling any write-capable functions such as print dispatch or
   virtual-printer workflows.

## Validation and troubleshooting

Render and validate the Compose model locally from the repository root:

```sh
docker compose --env-file bambuddy/.env.example -f bambuddy/compose.yaml config --quiet
```

On TrueNAS after deployment, inspect the container and its health check:

```sh
docker compose -f bambuddy/compose.yaml ps
docker compose -f bambuddy/compose.yaml logs --tail 100 bambuddy
```

If Traefik returns `502`, confirm the `bambuddy` container is healthy, joined
to the external `traefik` network, and that Traefik sees the router and service
in its dashboard. If Bambu Buddy cannot reach the printer, confirm the DHCP
reservation, printer LAN mode/access code, and that no VLAN/firewall rule
blocks TrueNAS-to-printer traffic.

## Backup and upgrades

Back up both directories together:

```text
/mnt/SSD/Containers/bambuddy/data
/mnt/SSD/Containers/bambuddy/logs
```

The `data` directory contains the SQLite database and archives; it is the
critical restore set. Include the logs for diagnosis. Preserve the MFA
encryption key in your secret manager or Portainer configuration alongside the
backup.

For upgrades, review the upstream [Bambu Buddy releases](https://github.com/maziggy/bambuddy/releases), create a backup, change `BAMBUDDY_VERSION` to the
reviewed release, then redeploy the stack through Portainer. Do not use the
application's in-app updater for this Git-managed Portainer stack.
