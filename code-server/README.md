# code-server

VS Code running in the browser, served from your homelab. Every device gets the same editor, extensions, terminals, and file access without installing anything locally — useful when working from a tablet, a borrowed machine, or anywhere you can't or don't want to sync a local dev environment.

**When to use this over a local VS Code install:** When you want a single persistent workspace (git clones, SSH keys, extensions, settings) that follows you across devices, or when your dev target (TrueNAS, a Proxmox VM, a container) is more naturally edited from the server side.

[https://docs.linuxserver.io/images/docker-code-server/]

## Architecture

```
Browser (HTTPS) → Traefik (TLS termination) → code-server:8443 (HTTP)
```

code-server listens on port 8443 internally. Traefik terminates TLS, so the browser gets a valid HTTPS connection. `PROXY_DOMAIN` tells code-server the public hostname so it generates correct internal URLs when running behind a reverse proxy.

## Prerequisites

- Traefik running and the `traefik` external network created
- Host storage directory created on TrueNAS:
  ```sh
  mkdir -p /mnt/SSD/Containers/code-server
  ```
- DNS record for `code.yourdomain.com` pointing to Traefik's IP (`10.0.5.5`)

## Quick Start

```sh
cp example.env .env
# Fill in CODESERVER_PASSWORD and optionally CODESERVER_SUDO_PASSWORD
docker compose up -d
```

Navigate to `https://code.yourdomain.com` and enter your password.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TZ` | `America/New_York` | Container timezone |
| `PUID` | `3001` | User ID for file permissions |
| `PGID` | `3001` | Group ID for file permissions |
| `CODESERVER_DOMAIN` | — | Public hostname (used by Traefik and `PROXY_DOMAIN`) |
| `CODESERVER_PASSWORD` | — | Plaintext web UI password |
| `CODESERVER_SUDO_PASSWORD` | — | Sudo password for the integrated terminal (optional) |

### Optional variables (add to `.env` as needed)

| Variable | Description |
|---|---|
| `HASHED_PASSWORD` | Argon2 or bcrypt hash — use instead of `PASSWORD` for better security |
| `SUDO_PASSWORD_HASH` | Hashed sudo password — use instead of `SUDO_PASSWORD` |
| `PWA_APPNAME` | Name shown when installing as a PWA (default: `code-server`) |

## Hashed Passwords

Storing plaintext passwords in `.env` is fine for a LAN-only setup, but if you prefer hashed credentials:

```sh
# Generate an argon2 hash (requires argon2 package)
echo -n "yourpassword" | argon2 $(openssl rand -base64 32) -e
```

Set `HASHED_PASSWORD` (and/or `SUDO_PASSWORD_HASH`) in `.env` and remove the plaintext `PASSWORD`/`SUDO_PASSWORD` variables.

## Workspace & Git

The default workspace is `/config/workspace` inside the container, which maps to `/mnt/SSD/Containers/code-server/workspace` on the host. Clone repos there to persist them across container recreations.

For GitHub/GitLab SSH access, place your private key at `/config/.ssh/id_rsa` (i.e. `/mnt/SSD/Containers/code-server/.ssh/id_rsa` on the host) before starting the container.
