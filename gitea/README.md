# Gitea on TrueNAS (Portainer)

Gitea is a self-hosted, lightweight Git service â€” think GitHub but running on your own hardware. It provides repository hosting, issue tracking, pull requests, CI/CD via Gitea Actions, a package registry, and a web-based code editor. It's written in Go, which means low memory usage (~150 MB at idle) and fast startup times.

**When does it make sense to run Gitea?**
- You want full control over your source code â€” no third-party has access
- You need private repositories without paying for a SaaS plan
- You want to mirror repositories from GitHub/GitLab for offline access or redundancy
- You're running a homelab CI/CD pipeline and want an on-prem trigger source
- You want to host packages (npm, Docker images, PyPI, etc.) alongside your code

Images in `compose.yaml` are frozen to the inventoried builds. See the [image update guide](../README.md#image-updates); `docker compose pull` alone does not upgrade them.

## Deployment status and upgrade gate (2026-10-31)

Gitea is already live on TrueNAS in Portainer stack **195**, environment **35**.
The inventoried app digest below is unchanged and reports **Gitea 1.27.3** when
run locally. The live database is PostgreSQL **17.11**. This proposed Compose
selects PostgreSQL **18.6**, and is safe for empty storage or a completed,
accepted logical migration only.

**Do not merge/deploy this database change directly onto the live stack.** Its
Git stack tracks `main` with automatic pull/redeployment. The operator must approve and run the live migration in the TrueNAS shell, pause Git polling/image
updaters, and complete the [controlled migration](#postgresql-17-to-18) before
merging and resuming automation. A green PR check is not cutover authorization.
No live migration or production backup/restore was performed for this PR.

## Architecture

```text
Internet / LAN
      â”‚
      â–¼
  Traefik (HTTPS :443)
      â”‚ Host(`gitea.yourdomain.com`)
      â–¼
  gitea (port 3000) â”€â”€â”€â”€ gitea-db (PostgreSQL :5432)
      â”‚
      â–¼
  SSH (host :2222 â†’ container :22)
```

- **gitea** â€” main application container. Serves the web UI, git-over-HTTPS, and SSH
- **gitea-db** â€” PostgreSQL 17 database on an internal `gitea` bridge network
- Web traffic goes through Traefik with TLS termination
- SSH is port-forwarded directly from the host (not proxied through Traefik)
- Both containers communicate over the internal `gitea` network; only `gitea` joins the external `traefik` network

## What this stack does

- Routes `https://gitea.virtuallyboring.com` through the existing Traefik
  network, with the existing `secure-headers@file` and `lan-only@file`
  middlewares. It is not Internet-accessible through Traefik.
- Publishes Git-over-SSH on TrueNAS TCP port `2222`. This is separate from
  Traefik and is reachable wherever the TrueNAS host is reachable; restrict it
  with host firewall rules if SSH must also be LAN-only.
- Stores Gitea repositories/configuration and PostgreSQL data on the SSD bind
  paths below. These are named volumes using the local bind driver, not
  anonymous Docker-managed storage.
- Disables self-service registration. Create the administrator in the first-run
  wizard, then use that account to invite users.

## Prerequisites

The following prerequisites and Quick Start are for a **new installation only**.
For the existing live stack, preserve all settings/keys and use the migration
procedure; do not run the first-install wizard or generate replacement secrets.

Create the host directories before starting:
Traefik must already own the external `traefik` bridge. Run Linux/Bash commands
from `gitea/`; never reinitialize restored paths with first-install steps.

```bash
mkdir -p /mnt/SSD/Containers/gitea/data
mkdir -p /mnt/SSD/Containers/gitea/db
```

The initial containers create the required ownership inside these directories.
Do not populate either directory with files from another Gitea/PostgreSQL
installation.

Confirm that no non-Docker service owns the planned SSH port:

```bash
ss -ltnp '( sport = :2222 )'
```

The current Gitea deployment owns its configured SSH mapping (default TCP
2222). The port check above is for a new installation, not evidence that the
live port is available to another service.

## Quick Start

1. Copy the environment template and replace every `replace-with-...` value:
   ```bash
   cp .env.example .env
   $EDITOR .env
   ```

2. Generate secrets:
   ```bash
   # Secret key (cookie encryption)
   openssl rand -hex 32

   # Internal token
   openssl rand -hex 64
   ```

3. In Portainer, select the `TrueNAS.virtuallyboring.com` environment and
   create a new **Git repository** stack from this repository. Set the Compose
   path to `gitea/compose.yaml`, add the values from `.env` as stack environment
   variables, then deploy. If deploying from the TrueNAS shell instead, run:
   ```bash
   docker compose up -d
   ```

4. Open `https://gitea.virtuallyboring.com` from the LAN. On first launch, use
   the **Installation** wizard to create the administrator and click **Install
   Gitea**. The database settings are supplied by Compose; do not expose port
   5432 or change its host to `localhost`.

5. Verify the Gitea container is healthy in Portainer, then clone a test
   repository over HTTPS and SSH. With the configured non-standard SSH port:

   ```bash
   git clone ssh://git@gitea.virtuallyboring.com:2222/<owner>/<repo>.git
   ```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GITEA_DOMAIN` | Yes | `gitea.virtuallyboring.com`; create a LAN DNS record pointing to Traefik |
| `GITEA_SSH_PORT` | Yes | Host port for SSH (default `2222`; host port 22 is usually the host OS) |
| `GITEA_DB_PASSWORD` | Yes | PostgreSQL password for the `gitea` user |
| `GITEA_SECRET_KEY` | Yes | 64-char hex key for cookie/session signing |
| `GITEA_INTERNAL_TOKEN` | Yes | 128-char hex token for internal API calls between Gitea processes |
| `GITEA_DISABLE_REGISTRATION` | No | Defaults to `true`; prevents LAN users from self-registering |
| `PUID` / `PGID` | No | UID/GID the Gitea process runs as (default `3001`) |
| `TZ` | No | Timezone (default `America/New_York`) |

## SSH Clone URLs

Clone URLs will look like:

```text
git clone ssh://git@gitea.virtuallyboring.com:2222/user/repo.git
git clone https://gitea.virtuallyboring.com/user/repo.git
```

You can add an `~/.ssh/config` entry to keep the short SSH URL syntax:

```text
Host gitea.virtuallyboring.com
    Port 2222
```

## Upgrading

Review exact image digests and release requirements before changing Compose.
Pulling an already pinned image fetches its bytes; it does not select an upgrade.
Keep application upgrades separate from database major upgrades. Both the
application `/data` tree and PostgreSQL are required for recovery.

### PostgreSQL 17 to 18

This is a **host-shell runbook for an approved maintenance window**, not commands
to run during PR review. Run as root in one Bash session on the verified TrueNAS
Docker host, from a dedicated private operator working directory. Export the
actual current PostgreSQL 17 Compose and all effective settings/overrides from
Portainer privately as `compose.yaml` and `.env` in that directory, validate
with `docker compose config --quiet`, and verify them against the running stack.
A Portainer Git stack does **not** imply a host checkout or `.env` exists. Do
not guess Portainer internal checkout paths or reconstruct secrets from defaults.
The full migration steps below assume that verified export has been prepared;
the initial read-only host preflight does not need it. Portainer inventory does
not establish host-shell access. The operator runs these commands; PR
preparation does not execute them.
Stop if the host or deployment settings cannot be verified.

The pinned application stays at the existing
`docker.gitea.com/gitea@sha256:87a67ee09d3ae0d1df5fda5dcda3e2a1f9236a45b0a59025d6e00e46adc43bef`
(Gitea 1.27.3). The [Gitea 1.27 database requirements](https://docs.gitea.com/1.27/installation/database-prep/)
include PostgreSQL 12 and newer. The documented range includes 18; it is not an
explicit vendor certification of this deployment. The selected PostgreSQL
`18.6@sha256:979bccfde35445db618c65107d27d08c6c21339d8dc3ad4c830c6633947be0e4`
was pulled and verified locally as 18.6 on 2026-10-31. Dependabot refreshed this digest during review; the rehearsal was rerun against
that exact final content, rather than relying on the moving tag.
The [official image](https://hub.docker.com/_/postgres) mounts
`/var/lib/postgresql` with `PGDATA=/var/lib/postgresql/18/docker` in 18.
Do not override `PGDATA` to open 17 files or merely move them into `18/docker`.
Use PostgreSQL's [logical major-version migration](https://www.postgresql.org/docs/18/upgrading.html).

**Approval and preflight gates:**

- Confirm the live stack/project, exact image IDs, both bind sources, existing
  environment variables and all deployed overrides. Preserve the current DB
  password, `SECRET_KEY`, `INTERNAL_TOKEN`, SSH host keys and original `app.ini`.
  Obtain a private settings export; this example assumes `.env` plus Compose.
  Do not invent a `.env` from defaults if Portainer owns the real values.
- Pause Portainer Git polling/redeployment, image updaters, scheduled backups
  and every external writer. Block incoming web/API/Git HTTPS and SSH traffic;
  stop/drain Actions runners and jobs, mirrors, migrations, hooks/integrations
  and any separate process touching the database or repositories. Stopping the
  Gitea container stops its own scheduled writers. Keep outbound integrations
  isolated during restored-instance testing to avoid sending real hooks/mail.
- Verify an independent off-host backup and an isolated restore with the actual
  data before cutover. Budget dump/restore time and space for two DB clusters,
  a complete cold app copy, image archives and the independent backup.
- The rename procedure below requires **ordinary directories**, not mountpoints
  or nested ZFS datasets. Inventory `findmnt`, `zfs list`, child mounts and
  external storage first. If either data tree includes a mounted dataset,
  symlink or separately mounted child, stop and prepare/rehearse a dataset-aware
  snapshot/clone/rollback procedure. Do not rename a mounted dataset directory.
- This example handles a dedicated cluster with only the default `gitea`
  login/owner role and `gitea` application database. Privately review roles and
  attributes, memberships, role/database settings, owners/ACLs, other databases,
  tablespaces, extensions, collation/encoding and custom server/HBA config.
  Any additions require a tailored migration and restore rehearsal first.
  `pg_dump` does not preserve cluster globals; retain `pg_dumpall --globals-only`
  as well. Do not blindly replay globals over the initializer's existing role.
  The default role is recreated from the unchanged settings with the same
  privileges/password. Custom roles/grants/settings must be restored explicitly
  before restoring their objects, and required PG18 extensions installed first.

**First operator checkpoint - read-only host preflight:** these commands do not
stop containers, read secret values, dump/query the database or change storage.
Run them on the TrueNAS host and check the service/project identity and mounts
against stack 195 / environment 35 before preparing any write commands.

```bash
hostname
for cmd in docker findmnt zfs mountpoint curl cp mv tar; do command -v "$cmd"; done
docker context show
docker compose version
docker info --format 'Name={{.Name}} OS={{.OperatingSystem}} Swarm={{.Swarm.LocalNodeState}}'
for container in gitea gitea-db; do
  docker inspect --format 'Name={{.Name}} ImageID={{.Image}} ImageRef={{.Config.Image}} State={{.State.Status}} Project={{index .Config.Labels "com.docker.compose.project"}} Service={{index .Config.Labels "com.docker.compose.service"}}' "$container"
  docker inspect --format '{{range .Mounts}}{{println .Type .Name .Source "->" .Destination}}{{end}}' "$container"
  for volume in $(docker inspect --format '{{range .Mounts}}{{if eq .Type "volume"}}{{println .Name}}{{end}}{{end}}' "$container"); do
    docker volume inspect --format 'Name={{.Name}} Type={{index .Options "type"}} Device={{index .Options "device"}} Options={{index .Options "o"}}' "$volume"
  done
done
for path in /mnt/SSD/Containers/gitea /mnt/SSD/Containers/gitea/data /mnt/SSD/Containers/gitea/db; do
  findmnt -T "$path" -n -o TARGET,SOURCE,FSTYPE
done
findmnt -rn -o TARGET,SOURCE,FSTYPE | awk '$1 ~ "^/mnt/SSD/Containers/gitea(/|$)"'
zfs list -H -o name,mountpoint | awk '$2 == "/" || $2 == "/mnt" || $2 == "/mnt/SSD" || $2 == "/mnt/SSD/Containers" || $2 ~ "^/mnt/SSD/Containers/gitea(/|$)"'
```

Confirm the DB is the inventoried `postgres:17.11` digest, app digest matches,
and actual bind sources are the expected `data` and `db`. The raw mount source
for a bind-backed named volume may appear as Docker's volume mountpoint; the
volume inspection above reports its underlying `device`. Do not infer the
bind source from a volume name. Stop on any discrepancy, mounted dataset or
extra storage and tailor the migration first. Do not share full `docker inspect`
or resolved Compose output, which can contain secrets.

**Second operator checkpoint:** explicitly pause and verify Portainer Git
polling/redeployment and all writers before proceeding below. Keep this PR
unmerged throughout preparation and cutover. Verify rollback access and the
independent backup, then authorize the planned downtime. Read-only preflight
output does not itself authorize database changes.

1. Save a private, versioned restore point **before replacing Compose**. Check
   that the project is shared by both services and the app is the exact reviewed
   image; an application mismatch needs separate review on PostgreSQL 17.

   ```bash
   set -eu
   umask 077
   root=/mnt/SSD/Containers/gitea
   command -v mountpoint >/dev/null
   test ! -L "$root"
   test ! -L "$root/db"
   test ! -L "$root/data"
   for path in "$root" "$root/db" "$root/data"; do
     if mountpoint -q "$path"; then
       echo 'Stop: use a dataset-aware migration for mounted storage.' >&2
       exit 1
     fi
   done
   # Review all child mounts/datasets; abort on any within these data trees.
   findmnt -rn -o TARGET,SOURCE,FSTYPE | awk '$1 ~ "^/mnt/SSD/Containers/gitea(/|$)"'
   zfs list -H -o name,mountpoint | awk '$2 == "/" || $2 == "/mnt" || $2 == "/mnt/SSD" || $2 == "/mnt/SSD/Containers" || $2 ~ "^/mnt/SSD/Containers/gitea(/|$)"'
   stamp=$(date -u +%Y%m%dT%H%M%SZ)
   backup="/mnt/SSD/Backups/gitea-pg18-$stamp"
   old_db_dir="$root/db.pg17-$stamp"
   test ! -e "$backup"
   test ! -e "$old_db_dir"
   test "$(cat "$root/db/PG_VERSION")" = 17
   mkdir -p "$backup"
   cp -p .env "$backup/settings.env"
   project=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' gitea-db)
   test -n "$project"
   test "$project" = "$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' gitea)"
   docker compose -p "$project" --env-file .env config > "$backup/compose.pg17.yaml"
   old_app=$(docker inspect --format '{{.Image}}' gitea)
   old_db=$(docker inspect --format '{{.Image}}' gitea-db)
   reviewed_app=docker.gitea.com/gitea@sha256:87a67ee09d3ae0d1df5fda5dcda3e2a1f9236a45b0a59025d6e00e46adc43bef
   docker pull "$reviewed_app"
   test "$old_app" = "$(docker image inspect --format '{{.Id}}' "$reviewed_app")"
   printf 'services:\n  gitea:\n    image: %s\n  gitea-db:\n    image: %s\n' \
     "$old_app" "$old_db" > "$backup/images.pg17.yaml"
   docker image save -o "$backup/images.tar" "$old_app" "$old_db"
   printf '%s\n' "$project" > "$backup/project-name"
   printf '%s\n' "$old_db_dir" > "$backup/old-db-path"
   docker compose -p "$project" exec -T gitea-db \
     psql -X -v ON_ERROR_STOP=1 -U gitea -d gitea \
       -c 'SHOW server_version;' -c 'SHOW data_directory;' \
       -c '\l+' -c '\du+' -c '\drds' -c '\db+' -c '\dx+' \
       -c 'TABLE pg_auth_members;' -c 'TABLE pg_db_role_setting;' \
       > "$backup/database-inventory.txt"
   ```

   Review the private inventory and original config against the gates above.
   Record current repository/issue/user counts and representative clone commit
   IDs, permissions, attachments, LFS objects and package artifacts for later
   comparison. Do not print credentials or commit the backup. Encrypt settings,
   globals (which contain role password hashes), data and dumps for off-host
   storage. Local image IDs plus `images.tar` make rollback independent of tags.

2. Stop all application writers before taking the logical database backup, then
   stop the database before copying app files. This keeps Git objects and DB
   metadata at one restore point, as required by [Gitea backup consistency](https://docs.gitea.com/1.27/administration/backup-and-restore/).
   Native PostgreSQL tools avoid the documented XORM dump limitations.

   ```bash
   docker compose -p "$project" stop gitea
   docker compose -p "$project" exec -T gitea-db \
     pg_dump --format=custom --create -U gitea -d gitea > "$backup/gitea.dump"
   docker compose -p "$project" exec -T gitea-db \
     pg_dumpall --globals-only -U gitea > "$backup/globals.sql"
   test -s "$backup/gitea.dump"
   test -s "$backup/globals.sql"
   docker compose -p "$project" exec -T gitea-db pg_restore --list \
     < "$backup/gitea.dump" > "$backup/dump-contents.txt"
   docker compose -p "$project" down         # Never add -v / --volumes
   cp -a "$root/data" "$backup/gitea-data"
   mv "$root/db" "$old_db_dir"
   mkdir "$root/db"
   ```

   Archive listing only checks format; restore/application checks prove usability.
   Keep the entire old PostgreSQL 17 directory intact with numeric ownership.
   The cold copy must include all `/data`: repositories, config/custom files,
   uploads/attachments, avatars, LFS, packages, SSH keys and Actions artifacts
   where present. Also back up any configured external/object storage, custom
   repo roots or separately mounted paths with the same consistency boundary;
   `/data` alone does not cover them. Do not blanket-chown DB files to the app UID.

3. Stage the **exact tested PR commit** in a separate directory while `main`
   still selects PostgreSQL 17. Get its full 40-character SHA from the PR review
   result, not from the moving branch name. Do not edit the Portainer checkout
   or pull `main` to obtain the proposed Compose. Keep Gitea stopped. Use the
   saved real environment plus explicit project name for this staged Compose:

   ```bash
   # Fill this with the exact tested full PR head supplied in the review result.
   reviewed_commit=REPLACE_WITH_TESTED_40_CHARACTER_PR_HEAD
   [[ "$reviewed_commit" =~ ^[0-9a-f]{40}$ ]]
   staged="$backup/reviewed-source"
   test ! -e "$staged"
   if command -v git >/dev/null; then
     git clone --no-checkout https://github.com/DanielBoring/HomeLab.git "$staged"
     git -C "$staged" checkout --detach "$reviewed_commit"
     test "$(git -C "$staged" rev-parse HEAD)" = "$reviewed_commit"
   else
     # No package installation on TrueNAS; this Compose has no relative files.
     command -v curl >/dev/null
     mkdir -p "$staged/gitea"
     curl --fail --show-error --location \
       "https://raw.githubusercontent.com/DanielBoring/HomeLab/$reviewed_commit/gitea/compose.yaml" \
       --output "$staged/gitea/compose.yaml"
   fi
   pg18() {
     docker compose -p "$project" --env-file "$backup/settings.env" \
       -f "$staged/gitea/compose.yaml" "$@"
   }
   ```

   Review the staged diff against the saved Compose and preserve any custom
   overrides before continuing. The staged model must select the unchanged app
   pin, the reviewed DB pin, the parent DB mount and the actual same bind sources.
   Restore into the **new empty cluster only**. `--clean --create` replaces the initializer's empty
   `gitea` database and preserves the dumped database metadata, owners and ACLs;
   it must never target the live original 17 cluster. The original `gitea` role
   must already exist with its original password before restoring. Stop on errors.

   ```bash
   pg18 config --quiet
   pg18 pull gitea-db
   pg18 up -d gitea-db
   # Wait for readiness; inspect logs and rerun readiness if still initializing.
   pg18 exec -T gitea-db pg_isready -U gitea -d postgres
   pg18 exec -T gitea-db \
     pg_restore --exit-on-error --clean --if-exists --create -U gitea -d postgres \
     < "$backup/gitea.dump"
   pg18 exec -T gitea-db \
     psql -X -v ON_ERROR_STOP=1 -U gitea -d gitea \
       -c 'ANALYZE;' -c 'SHOW server_version;' -c 'SHOW data_directory;' \
       -c '\l+' -c '\du+' -c '\drds' -c '\dx+'
   ```

   Confirm 18.6 and `/var/lib/postgresql/18/docker`, compare the saved inventory,
   ownership/ACLs, extensions, collation/encoding and expected row counts. The
   bind source remains host `db`; only the container mount changes to the parent.
   `POSTGRES_PASSWORD` initializes empty storage; changing it does not rotate an
   existing role. No password, key, token or SSH host-key rotation belongs here.

4. Start Gitea while clients, external traffic and runners remain blocked.
   Check health and logs, authenticated web login, users/permissions, issues and
   representative repository history. Verify HTTPS **and SSH** clone/push with
   an approved disposable repository, and compare existing SSH host fingerprints.
   Verify attachments/uploads, LFS fetch, packages and Actions state if used;
   avoid running real pipelines, mirrors or hooks during acceptance. Recreate the
   database and application, then recheck persistence. Only reopen clients and
   resume automation after acceptance and an agreed rollback decision.

   ```bash
   pg18 up -d gitea
   pg18 ps
   pg18 logs --tail=100 gitea gitea-db
   # After the first acceptance checks, verify persistence across recreation.
   pg18 stop gitea
   pg18 up -d --force-recreate gitea-db
   pg18 exec -T gitea-db pg_isready -U gitea -d gitea
   pg18 up -d --force-recreate gitea
   ```

   With Git polling still paused, confirm the controlled migration and all
   acceptance checks with the reviewer. Keep PR #18 unmerged until that report
   and separate merge approval. After merge, reconcile the actual Portainer Git
   stack to the accepted `main` Compose/settings/project/volumes; verify that
   adoption keeps the running image IDs and correct data mounts. Only then
   resume polling. Do not leave CLI-staged deployment and Portainer competing
   for the same stack. Retain the old DB,
   cold app state and independent backup through the agreed rollback window.

**Rollback before normal writes resume:** stop 18, preserve its state tree, and
restore the cold app copy together with the original PG17 directory, settings
and saved image IDs. Never point PostgreSQL 17 at 18's files. These commands use
the same saved variables and require the ordinary-directory preflight above.

```bash
pg18 down                                  # No -v
test ! -e "$root/db.pg18-failed-$stamp"
test ! -e "$root/data.pg18-failed-$stamp"
mv "$root/db" "$root/db.pg18-failed-$stamp"
mv "$old_db_dir" "$root/db"
mv "$root/data" "$root/data.pg18-failed-$stamp"
cp -a "$backup/gitea-data" "$root/data"
docker image load -i "$backup/images.tar"
docker compose -p "$project" --env-file "$backup/settings.env" \
  -f "$backup/compose.pg17.yaml" -f "$backup/images.pg17.yaml" \
  up -d --pull never gitea-db
# Wait for PostgreSQL readiness before starting Gitea.
docker compose -p "$project" --env-file "$backup/settings.env" \
  -f "$backup/compose.pg17.yaml" -f "$backup/images.pg17.yaml" \
  exec -T gitea-db pg_isready -U gitea -d gitea
docker compose -p "$project" --env-file "$backup/settings.env" \
  -f "$backup/compose.pg17.yaml" -f "$backup/images.pg17.yaml" \
  up -d --pull never gitea
```

Recheck login, issues, permissions, files, repository history and both clone
transports. Restore the actual Portainer deployed Compose/settings and old Git
reference before allowing automatic deployment again. After normal writes have
resumed on 18, the old 17 state is stale: this rollback loses those writes. Stop
and plan reconciliation instead of restoring it as though it were current.

### Rehearsal evidence and limits (2026-10-31)

A disposable Docker Desktop Linux rehearsal used the exact Gitea and PostgreSQL
17.11/18.6 digests, unique local volumes and one internal network with no
published ports, host data, Docker socket or external integrations. It created
a synthetic admin, private repository, Git commit and issue on 17; stopped the
app, dumped the DB/globals and cold-copied the full app tree; restored to 18;
verified authenticated API/issue reads and HTTP/SSH clones, a new HTTP push,
persistence after DB/app recreation, and rollback to the original 17 volume
plus the cold app tree. Rollback intentionally lost the 18-only test commit.

This validates the tested synthetic path. It does **not** validate production
backup recoverability, actual role/extension/config scope, TrueNAS ZFS/bind
ownership, Portainer adoption, Traefik/TLS, external storage, real hooks/runners,
LFS/packages/uploads functionality or every application feature. Those remain
live preflight/isolated-restore/acceptance gates, not assumed successes.

## Backup and recovery

For the inventoried live PostgreSQL 17 stack, [backup-before-pg18.sh](backup-before-pg18.sh)
creates private logical/cold backups and saves the original images; it does not
migrate or upgrade anything. Download the reviewed script **outside** the empty
backup directory. It requires explicit confirmation that GitOps is paused and
backup downtime is approved, and attempts to restart the same original DB/app
containers on failure. The selected local backup is on the same pool. Archive
listings/checksums are not restore verification; verify recovery separately and
preserve a private export of the actual Portainer Compose/settings/overrides.

Back up both `/mnt/SSD/Containers/gitea/data` and the matching PostgreSQL cluster
(`/mnt/SSD/Containers/gitea/db`, now containing `18/docker`) at one stopped-writer
restore point. Include original image archives, settings, keys and any external
storage. Follow the [shared isolated restore procedure](../README.md#backing-up-data)
and the version-specific migration/rollback guidance above. A database dump
alone omits repository files; repositories alone omit users/issues/permissions.
