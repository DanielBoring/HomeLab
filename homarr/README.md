# Homarr

Homarr is a self-hosted dashboard for organizing homelab apps and services. It provides a drag-and-drop UI, built-in Docker integration, health/status widgets, and app tiles without maintaining a large YAML dashboard by hand.

Images in `compose.yaml` are frozen to the inventoried builds. See the [image update guide](../README.md#image-updates); `docker compose pull` alone does not upgrade them.

## Architecture

```text
Browser
  |
  v
Traefik (TLS termination, lan-only)
  |
  v
homarr:7575
  |
  +-- /appdata persisted on the host
  +-- /var/run/docker.sock mounted read-only for Docker integration
```

## Prerequisites

Deploy Traefik first. Run Linux/Bash commands from `homarr/`.

Create the host data directory before first deploy:

```bash
mkdir -p /mnt/SSD/Containers/homarr
```

Generate a stable encryption key and store it in `.env`:

```bash
openssl rand -hex 32
```

Preserve `SECRET_ENCRYPTION_KEY` with the deployment; do not replace it without
a supported migration procedure for existing encrypted integration secrets.

## Quick Start

```bash
cp .env.example .env
$EDITOR .env
docker compose up -d
```

Access Homarr at `https://${HOMARR_DOMAIN}`.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `HOMARR_DOMAIN` | Yes | Traefik domain for the web UI |
| `SECRET_ENCRYPTION_KEY` | Yes | 64-character hex key for encrypting stored integration secrets |

## Notes

- The Docker socket has a read-only filesystem mount, but that does not prevent Docker API writes. Treat Homarr's socket access as privileged; restrict who can use its Docker integration or provide a suitably restricted API proxy.
- The healthcheck uses `/api/health/live`, not `/`. Hitting `/` as an unauthenticated healthcheck can trigger repeated `No home board found` errors in Homarr logs because the homepage route tries to resolve a default board.

## Recovery and updates

Check `docker compose ps`/recent `homarr` logs and verify authenticated boards
and integration widgets. Stop writers before preserving the complete appdata
path, original encryption key, other private settings and image pins. Use the
[shared recovery procedure](../README.md#backing-up-data), restore privately at
the same version with original ownership, and verify boards and decryption before
enabling Docker controls. Review app/database migrations before updates.
