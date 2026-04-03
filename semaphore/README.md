# Semaphore

Self-hosted UI for running Ansible, Terraform, OpenTofu, and Bash playbooks. Provides task scheduling, access control, and run history.

## Services

| Service | Port | Description |
|---|---|---|
| Semaphore | 3003 | Web UI |

## Prerequisites

Create the persistent storage directories before deploying:

```bash
mkdir -p /mnt/SSD/Containers/semaphore/{data,config,tmp}
```

> Semaphore manages its own internal permissions — no `chown` required.

## Quick Start

### 1. Copy the environment template

```bash
cp .env.example .env
```

### 2. Edit the .env file

```bash
nano .env
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `SEMAPHORE_ADMIN_PASSWORD` | Yes | — | Admin account password |
| `SEMAPHORE_ADMIN` | No | `admin` | Admin username |
| `SEMAPHORE_ADMIN_NAME` | No | `Admin` | Admin display name |
| `SEMAPHORE_ADMIN_EMAIL` | No | `admin@localhost` | Admin email |
| `SEMAPHORE_PORT` | No | `3003` | Host port for the web UI |

### 3. Deploy

```bash
docker compose up -d
```

### 4. Verify

```bash
docker compose ps
docker compose logs -f semaphore
```

Navigate to `http://<host-ip>:3003` and log in with your admin credentials.

## Storage

| Data | Path |
|---|---|
| Database, project data | `/mnt/SSD/Containers/semaphore/data` |
| Configuration files | `/mnt/SSD/Containers/semaphore/config` |
| Cloned repos, inventory cache | `/mnt/SSD/Containers/semaphore/tmp` |

## Included Tools

Semaphore v2.17.26 ships with:

| Tool | Version |
|---|---|
| Ansible | 2.18.11 |
| Terraform | 1.10.2 |
| OpenTofu | 1.10.0 |
| PowerShell | 7.5.0 |

## Maintenance

### Update image

Edit `compose.yaml` to bump the image tag, then:

```bash
docker compose pull
docker compose up -d
```

### Backup

```bash
docker compose down
tar -czf semaphore-backup-$(date +%Y%m%d).tar.gz \
  /mnt/SSD/Containers/semaphore/data \
  /mnt/SSD/Containers/semaphore/config
docker compose up -d
```

The `tmp` directory contains only cached/cloned content and does not need to be backed up.
