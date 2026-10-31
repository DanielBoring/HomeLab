# code-server

VS Code running in the browser, served from your homelab. Every device gets the same editor, extensions, terminals, and file access without installing anything locally — useful when working from a tablet, a borrowed machine, or anywhere you can't or don't want to sync a local dev environment.

**When to use this over a local VS Code install:** When you want a single persistent workspace (git clones, SSH keys, extensions, settings) that follows you across devices, or when your dev target (TrueNAS, a Proxmox VM, a container) is more naturally edited from the server side.

[LinuxServer image documentation](https://docs.linuxserver.io/images/docker-code-server/)

## Architecture

```text
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
cp .env.example .env
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
| `HASHED_PASSWORD` | Upstream-supported Argon2 web password hash; takes precedence over plaintext `CODESERVER_PASSWORD` |
| `SUDO_PASSWORD_HASH` | Hashed sudo password — use instead of `CODESERVER_SUDO_PASSWORD` |
| `PWA_APPNAME` | Name shown when installing as a PWA (default: `code-server`) |

## Hashed Passwords

Compose now explicitly passes these optional values. Generate a supported hash
privately using the linked image instructions, not a literal password in shell
history. Use single-quoted dotenv hash values so `$` characters are literal.
Keep a tested login path while switching: set `HASHED_PASSWORD` and/or
`SUDO_PASSWORD_HASH`, clear the matching `CODESERVER_PASSWORD` /
`CODESERVER_SUDO_PASSWORD` only after confirming the hashes work. A web hash and
Unix sudo hash use different formats; do not substitute one for the other.
Protect `.env` even with hashes and never leave authentication unintentionally
empty.

## Workspace & Git

The default workspace is `/config/workspace` inside the container, which maps to `/mnt/SSD/Containers/code-server/workspace` on the host. Clone repos there to persist them across container recreations.

For GitHub/GitLab SSH access, place your private key at `/config/.ssh/id_rsa` (i.e. `/mnt/SSD/Containers/code-server/.ssh/id_rsa` on the host) before starting the container.

## Operations and recovery

Run Linux commands from `code-server/`; give the selected PUID/PGID access to
fresh config/workspace paths without changing existing repository ACLs. Protect
SSH keys with user-only permissions and do not paste them into shared terminals.
The editor terminal can execute commands against mounted files; sudo access is
an additional privilege, not required for routine editing.

Check `docker compose ps` and `docker compose logs --tail 100 code-server`,
then verify authenticated access and a workspace file. Stop editing and the
container before preserving the whole config/workspace tree, SSH keys, original
settings and image reference using the
[shared recovery procedure](../README.md#backing-up-data). Restore privately at
the same version, verify projects/settings and login, and review extension
compatibility before updates.
