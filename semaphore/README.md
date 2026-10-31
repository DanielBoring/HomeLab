# Semaphore

[Semaphore](https://semaphoreui.com) is a self-hosted UI for running Ansible, Terraform, OpenTofu, and Bash automation. It adds scheduling, run history, access control, and a git-backed task system on top of your existing playbooks — without requiring any changes to them.

Run it when you want to trigger Ansible playbooks from a browser or schedule them on a cron, share automation access with others without giving them SSH access to your hosts, or just keep a history of what ran and what it output.

Images in `compose.yaml` are frozen to the inventoried builds. See the [image update guide](../README.md#image-updates); `docker compose pull` alone does not upgrade them.

## Architecture

```text
Browser → Traefik (TLS + lan-only) → semaphore :3000
```

Single container using SQLite. No external database required. All project data, keys, and inventory live in the bind-mounted data volume.

## Prerequisites

Run Bash on the Linux host from `semaphore/`; deploy Traefik first.
For fresh directories only:

```bash
mkdir -p /mnt/SSD/Containers/semaphore/{data,config,tmp}
chown 1001:0 /mnt/SSD/Containers/semaphore/{data,config,tmp}
```

The pinned release's [Dockerfile](https://github.com/semaphoreui/semaphore/blob/v2.17.26/deployment/docker/server/Dockerfile)
uses UID 1001 with group 0 (checked 2026-10-13). Host bind mounts hide the image's
pre-created ownership. Preserve restored ACLs/owners; do not chown database files
to the repository's standard UID 3001.

## Deployment

### 1. Configure environment

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `TZ` | Timezone (default: `America/New_York`) |
| `SEMAPHORE_DOMAIN` | FQDN Traefik routes to Semaphore (e.g. `semaphore.virtuallyboring.com`) |
| `SEMAPHORE_PORT` | Host port for direct access (default: `3003`) |
| `SEMAPHORE_ADMIN_PASSWORD` | Admin password — only applied on first run |
| `SEMAPHORE_ADMIN` | Admin username (default: `admin`) |
| `SEMAPHORE_ADMIN_NAME` | Admin display name (default: `Admin`) |
| `SEMAPHORE_ADMIN_EMAIL` | Admin email (default: `admin@localhost`) |

### 2. Start

```bash
docker compose up -d
docker compose logs -f semaphore
```

### 3. Access

- **Via Traefik:** `https://<SEMAPHORE_DOMAIN>` (LAN only)
- **Direct:** `http://<host-ip>:3003`

## Initial Configuration

Log in with the admin credentials from `.env`. The admin password is only read on first start — changing it in `.env` after the database exists has no effect. Use the UI to change it afterward.

Semaphore organises automation into **Projects**. Everything below — keys, inventory, repositories, templates — lives inside a project.

### 1. Create a project

Click **New Project**, give it a name (e.g. `HomeLab`), and save. You'll land on the project dashboard.

### 2. Add a Key Store entry

The Key Store holds credentials Semaphore uses to connect to managed hosts or pull from private git repos.

Go to **Key Store → New Key**:

| Field | Notes |
|---|---|
| Name | Friendly label (e.g. `homelab-ssh-key`) |
| Type | `SSH Key` for Ansible over SSH; `Password` for username+password auth |
| Private Key | Paste your SSH private key (the `id_ed25519` or `id_rsa` content) |

### 3. Add a Repository

Semaphore clones your playbook repo before each run. Go to **Repositories → New Repository**:

| Field | Notes |
|---|---|
| Name | e.g. `homelab-playbooks` |
| URL | Git remote URL (HTTPS or SSH) |
| Branch | Branch to clone (e.g. `main`) |
| Access Key | Select the key from step 2 if the repo is private; `None` for public |

### 4. Add an Inventory

Inventory tells Ansible which hosts to target. Go to **Inventory → New Inventory**:

| Field | Notes |
|---|---|
| Name | e.g. `homelab-hosts` |
| Type | `Static` for a hosts file; `File` to point at a file in the repo |
| User Credentials | SSH key from step 2 |
| Static inventory | Paste your inventory in INI or YAML format |

### 5. Create a Task Template

Templates are the core unit — they bind a playbook to an inventory, key, and environment. Go to **Task Templates → New Template**:

| Field | Notes |
|---|---|
| Name | e.g. `Update all hosts` |
| Playbook | Path to the playbook within the repo (e.g. `update.yml`) |
| Inventory | Select from step 4 |
| Repository | Select from step 3 |
| Environment | Optional JSON extra-vars (can be left empty) |

### 6. Run a task

Click **Run** on the template. Semaphore clones the repo, builds the Ansible command, streams output in real time, and stores the result in the run history.

## Included Tools

The release Dockerfile includes Ansible, Terraform, OpenTofu and Terragrunt.
Exact binary versions should be checked in the deployed image before selecting
playbooks; they have not been independently inventoried here. Do not assume
PowerShell is installed because Semaphore supports a PowerShell task type.

## Storage

| Path | Contents |
|---|---|
| `/mnt/SSD/Containers/semaphore/data` | SQLite database, project data |
| `/mnt/SSD/Containers/semaphore/config` | Configuration files |
| `/mnt/SSD/Containers/semaphore/tmp` | Cloned repos, inventory cache (expendable) |

## Updating

Review [releases](https://github.com/semaphoreui/semaphore/releases), take a
recoverable backup and update both the reviewed tag and digest before pulling:

```bash
docker compose pull
docker compose up -d
```

## Backup

Stop scheduled tasks and the container before preserving `data` and `config`,
original image pins and encrypted settings/keys. Follow the
[shared recovery procedure](../README.md#backing-up-data). `tmp` is expendable.
Restore to fresh destinations with UID 1001 access and original versions; verify
login, projects, inventories and key-store access without launching jobs against
managed hosts. Resume scheduling only after verification.
