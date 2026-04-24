# Termix

[Termix](https://github.com/lukegus/termix) is a lightweight, web-based terminal manager. It lets you define named SSH connections and open browser-based terminal sessions to your hosts — no client software or exposed SSH ports required on the accessing device.

Run it when you want a quick way to reach your homelab hosts from any browser (a phone, a borrowed laptop, a tablet) without setting up a full bastion or VPN client. It's not a replacement for proper SSH access from a trusted machine, but it fills the gap for casual, LAN-side access.

## Architecture

```
Browser → Traefik (TLS + lan-only) → Termix :8080
                                         ↓
                                    SSH to hosts
```

Termix runs as a single container. It holds no secrets itself — connection details (hostnames, credentials) are configured in the UI and stored in the data volume at `/app/data`. The container sits on the `traefik` network and is restricted to LAN access only via the `lan-only` middleware.

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

Hosts can be organized with tags and folders if you have many. Once added, click the host to open a terminal session in the browser.

### 3. Remote desktop (optional)

RDP, VNC, and Telnet support requires a `guacd` sidecar container. This compose file does not include it — if you need remote desktop, add the following service and connect it on a shared network:

```yaml
guacd:
  image: guacamole/guacd:1.6.0
  container_name: guacd
  restart: unless-stopped
```

SSH-only use cases (the common homelab case) do not need guacd.

## Updating

```bash
docker compose pull
docker compose up -d
```
