# Termix

[Termix](https://github.com/lukegus/termix) is a web-based server management platform with SSH terminal and remote desktop (RDP/VNC) capabilities. It lets you define named connections and open browser-based sessions to your hosts — no client software required on the accessing device.

Run it when you want a quick way to reach your homelab hosts from any browser (a phone, a borrowed laptop, a tablet) without setting up a full bastion or VPN client.

## Architecture

```
Browser → Traefik (TLS + lan-only) → termix :8080
                                         ↓
                              ┌──────────┴──────────┐
                         SSH to hosts          guacd :4822
                                                    ↓
                                          RDP/VNC to hosts
```

Two containers:
- **termix** — web frontend; joined to both `termix` and `traefik` networks
- **guacd** — Guacamole proxy daemon that handles RDP/VNC/Telnet protocol translation; internal `termix` network only, not exposed to the host

Termix discovers guacd by container name via Docker DNS. No env var configuration is required — they just need to share the `termix` network.

## Prerequisites

- Traefik running with the `traefik` external network created
- `/mnt/SSD/Containers/termix` directory created on the host

```bash
sudo mkdir -p /mnt/SSD/Containers/termix
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
| `TERMIX_DOMAIN` | FQDN Traefik will route to Termix (e.g. `termix.virtuallyboring.com`) |

### 2. Start

```bash
docker compose up -d
docker compose logs -f termix
```

### 3. Access

- **Via Traefik:** `https://<TERMIX_DOMAIN>` (LAN only)
- **Direct:** `http://<host-ip>:8090`

## Initial Configuration

On first visit, Termix will prompt you to create an admin account. Do this immediately — the UI is unauthenticated until an account exists.

### 1. Create your admin account

Fill in a username and password. This becomes the primary admin user. Enable **2FA (TOTP)** at this step or from account settings afterward — recommended since this is a terminal interface.

### 2. Add SSH hosts

Navigate to **Connections → Add New** and fill in:

| Field | Notes |
|---|---|
| Name | Friendly label shown in the UI |
| Host | IP or hostname of the target machine |
| Port | SSH port (default: `22`) |
| Username | SSH user on the target |
| Auth | Password or SSH private key (key is preferred) |

### 3. Add RDP hosts (Windows Servers)

Navigate to **Connections → Add New** and set the protocol to **RDP**, then fill in:

| Field | Notes |
|---|---|
| Name | Friendly label |
| Host | IP or hostname of the Windows Server |
| Port | RDP port (default: `3389`) |
| Username | Windows username (e.g. `Administrator` or `DOMAIN\user`) |
| Password | Windows password |
| Security | `NLA` for modern Windows; fall back to `Any` if NLA fails |
| Ignore cert | Enable if using a self-signed certificate |

RDP connections are proxied through guacd — if guacd is not running, the connection will fail silently. Verify with `docker compose ps` that guacd is up.

## Updating

```bash
docker compose pull
docker compose up -d
```
