# Paperless PostgreSQL 17 to 18 migration

This is an operator runbook for the existing Portainer Git stack `paperless-ngx`
on `TrueNAS.virtuallyboring.com` (environment 35, stack 136). It is **not** a
normal image pull. PostgreSQL 18 cannot use the PostgreSQL 17 data files
directly, and the official image changes its data path to
`/var/lib/postgresql/18/docker` under a mount at `/var/lib/postgresql`.
Do not deploy the new Compose until the logical restore and acceptance steps
below are ready. Portainer Git polling is paused globally; keep it paused
through migration, merge, adoption, and verification.

The current live app is the exact `ghcr.io/paperless-ngx/paperless-ngx:3.3.0`
digest in `compose.yaml`. A read-only runtime check on 2026-11-01 showed its
effective Django engine is PostgreSQL, database `paperless` on host `db`, despite
`PAPERLESS_DBENGINE` being absent. The [exact v3.3.0 source](https://github.com/paperless-ngx/paperless-ngx/blob/v3.3.0/src/paperless/settings/custom.py#L1316-L1329)
infers PostgreSQL from `PAPERLESS_DBHOST` in this case, although the current
general documentation says to set the engine explicitly. The live PG17
database has 75 public tables, three user records and zero document records.
**Zero documents does not make the database
disposable:** accounts, configuration, mail rules, workflows, and task state may
still be present. This PR keeps the known-running app configuration and exact image
pin; review any Paperless app upgrade separately.

The read-only source inventory found PostgreSQL 17.11, UTF8, libc locale
`en_US.utf8`, collation version `2.41`, one custom role (`paperless`), only the
default `plpgsql` extension, no non-default tablespace location, and no
database-specific role settings. The six storage directories share the
`SSD/Containers` ZFS dataset, use NFSv4 ACLs, and have no nested mounts.
Approximate observed sizes: `db` 30 MB, `data` 3.8 MB, `media` 2.5 KB; the
other three directories are smaller. These are a snapshot, not substitute
for a fresh cutover inventory.

## Stop conditions and inventory

Before downtime, verify and record privately:

- The actual Portainer stack ID, endpoint, Git reference and deployed commit;
  the Compose project `paperless-ngx`; the exact five running image IDs,
  container labels, health, mounts, volume options, environment **key names**,
  networks, published port and any overrides. Do not print secret values.
- PostgreSQL `server_version`, `data_directory`, database encoding/collation,
  roles, extensions, tablespaces, database size and representative counts
  (users, documents, tags, mail rules and workflows). Confirm the app's
  effective database engine and absence of `data/db.sqlite3` again.
- All six host directories under `/mnt/SSD/Containers/paperless` (`db`, `data`,
  `media`, `consume`, `export`, `redis`), their owners, ACLs, child mounts,
  symlinks, sizes and available space. The observed DB root is UID/GID
  `999:999`, mode `0700`; app directories use UID/GID `3001:3001`.
- The backup destination and recovery method selected in the maintenance
  approval. Prefer a separate pool or off-host copy and an isolated restore
  check. A same-pool-only choice requires explicit acceptance of pool-loss
  exposure for Paperless; the Gitea exception does not carry over. A checksum
  or archive listing is not a restore test. If an isolated restore is deferred,
  record that reduced recovery confidence in the same approval.
- An agreed maintenance window and a way to block web uploads, API clients,
  consume-file delivery, email ingestion and any other writers. Keep those
  sources blocked until acceptance or rollback ends.

Stop if any fact differs, the approved backup is incomplete, an
extension/tablespace or external storage is unaccounted for, the new storage
cannot be accessed by the image's PostgreSQL UID, or a selected restore check
fails. Never use `down -v`.

## Stage the reviewed Compose and recovery material

Use an empty root-owned `0700` directory **outside the repository** for private
settings and backup artifacts. Obtain the exact deployed PG17 Compose from
Portainer and the exact reviewed 40-character PR commit's PG18 Compose. Verify
their diff changes only the DB image and DB mount. Do not use a moving branch
name for this staging step. Export the actual Portainer environment and any
overrides privately; `.env.example` is not a source of live values. Keep the
original image IDs and `docker image save` archives of all five images so
rollback cannot accidentally pull new tags. Prefer to check an isolated
restore on a separate host or equivalent dataset before relying on the
recovery copy; explicitly record any decision to defer that test.

The commands below assume these private files already exist, were reviewed,
and have mode `0600` (directory `0700`):

```text
$backup/settings.env              actual effective stack values, private
$backup/compose.pg17.yaml        Portainer-deployed original Compose
$backup/compose.pg18.yaml        exact reviewed PR commit Compose
$backup/images.pg17.yaml        image-ID overrides for all five old services
$backup/images.tar              original local image archives
```

Set these in a root shell on **TrueNAS only** after checking the local Docker
context, source paths and free space. A wrong Docker context or project name
must stop the procedure:

```bash
set -euo pipefail
umask 077
root=/mnt/SSD/Containers/paperless
backup=/ABSOLUTE/PRIVATE/INDEPENDENT-BACKUP-PATH
test "$(hostname)" = TrueNAS
test "$(id -u)" = 0
test "$(docker context show)" = default
test "$(docker --host unix:///var/run/docker.sock info --format '{{.OSType}}')" = linux
test "$(realpath -e "$root")" = "$root"
test "$(realpath -e "$backup")" = "$backup"
test "$backup" != "$root"
case "$backup/" in
  "$root/"*) printf 'Backup is inside source.\n' >&2; exit 1 ;;
esac
case "$root/" in
  "$backup/"*) printf 'Backup contains source.\n' >&2; exit 1 ;;
esac
test "$(stat -c '%u:%a' "$backup")" = 0:700
test "$(cat "$root/db/PG_VERSION")" = 17
old() { docker --host unix:///var/run/docker.sock compose -p paperless-ngx \
  --env-file "$backup/settings.env" -f "$backup/compose.pg17.yaml" "$@"; }
new() { docker --host unix:///var/run/docker.sock compose -p paperless-ngx \
  --env-file "$backup/settings.env" -f "$backup/compose.pg18.yaml" "$@"; }
wait_db_ready() {
  local i
  for ((i=0; i<90; i++)); do
    if docker --host unix:///var/run/docker.sock exec paperless-db \
      sh -ec 'test "$(cat /proc/1/comm)" = postgres' >/dev/null 2>&1 && \
      docker --host unix:///var/run/docker.sock exec paperless-db \
      pg_isready -h 127.0.0.1 -U paperless -d paperless >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  printf 'PostgreSQL did not reach final TCP readiness.\n' >&2
  return 1
}
old config --quiet
new config --quiet
new pull db
pg18=postgres:18.6@sha256:979bccfde35445db618c65107d27d08c6c21339d8dc3ad4c830c6633947be0e4
test "$(docker --host unix:///var/run/docker.sock run --rm --network none \
  --entrypoint id "$pg18" -u postgres)" = 999
test "$(docker --host unix:///var/run/docker.sock run --rm --network none \
  --entrypoint id "$pg18" -g postgres)" = 999
docker --host unix:///var/run/docker.sock run --rm --network none \
  --entrypoint locale "$pg18" -a | grep -Fxq en_US.utf8
```

Privately compare both rendered models and runtime settings. Check all volume
sources, image references and ports. The DB mount alone must move from
`/var/lib/postgresql/data` to `/var/lib/postgresql`; the host source remains
`$root/db`. Preserve all other service pins and settings. Record the original
PG17 volume `paperless-ngx_paperless-db` and its bind options. If a Portainer
override exists, stage it explicitly in both models and re-review the diff.

### Prove PG18 storage access before stopping the live app

The TrueNAS dataset uses NFSv4 ACLs. A directory with numeric mode `0700` can
still fail to traverse after ACL inheritance. Run this **separate disposable
directory** probe with the exact PG18 image and its actual UID/GID before
cutover. Do not point the probe at the live `db` directory:

```bash
probe_pg18_storage() {
  local source=$1
  docker --host unix:///var/run/docker.sock run --rm --pull never \
    --network none --user 999:999 --cap-drop ALL \
    --security-opt no-new-privileges:true \
    --mount "type=bind,src=$source,dst=/var/lib/postgresql" \
    --entrypoint /bin/sh \
    "$pg18" \
    -ec 'p=$(mktemp /var/lib/postgresql/18/docker/.probe.XXXXXXXX); printf ok > "$p"; test "$(cat "$p")" = ok; rm "$p"'
}
probe=$(mktemp -d "$root/.pg18-access.XXXXXXXX")
mkdir "$probe/18" "$probe/18/docker"
chown 999:999 "$probe" "$probe/18" "$probe/18/docker"
chmod 700 "$probe" "$probe/18" "$probe/18/docker"
probe_pg18_storage "$probe"
rmdir "$probe/18/docker" "$probe/18" "$probe"
```

Retain a failed probe directory for inspection; do not recursively delete it.
The app UID `3001` must never be applied to PostgreSQL storage. Verify the
PG18 image's actual PostgreSQL UID/GID before using `999:999` above.

## Quiesce and capture a consistent restore point

Block all external writers first. A Paperless `document_exporter` export is a
useful second recovery route, but it omits API tokens and is version specific;
it does not replace the cold six-directory and native database backup. Perform
the export only after document consumption and other writers are quiesced, then
check its exit status and contents privately.

Stop the webserver before the final native dump. PostgreSQL remains up long
enough for `pg_dump`; verify no other client writers remain. Do not echo
credentials or put them in a command line. Capture role globals for inventory,
but do not blindly restore them into the new cluster, whose app role is created
from the existing private environment.

```bash
old stop webserver
clients=$(old exec -T db psql -X -w -At -v ON_ERROR_STOP=1 -U paperless -d paperless \
  -c "SELECT count(*) FROM pg_stat_activity WHERE backend_type='client backend' AND pid <> pg_backend_pid();")
test "$clients" = 0
old exec -T db pg_dump --format=custom --create -U paperless -d paperless \
  > "$backup/paperless.pg17.dump"
old exec -T db pg_dumpall --globals-only -U paperless \
  > "$backup/globals.private.sql"
test -s "$backup/paperless.pg17.dump"
test -s "$backup/globals.private.sql"
old exec -T db pg_restore --list < "$backup/paperless.pg17.dump" \
  > "$backup/dump-contents.private.txt"
clients=$(old exec -T db psql -X -w -At -v ON_ERROR_STOP=1 -U paperless -d paperless \
  -c "SELECT count(*) FROM pg_stat_activity WHERE backend_type='client backend' AND pid <> pg_backend_pid();")
test "$clients" = 0
old down                         # never add -v / --volumes
test "$(cat "$root/db/PG_VERSION")" = 17
tar --no-acls --xattrs --xattrs-include='*' --numeric-owner --sparse --one-file-system \
  -C "$root" -cpf "$backup/paperless-files.cold.tar" \
  data media consume export redis
tar --no-acls --xattrs --xattrs-include='*' --numeric-owner --sparse --one-file-system \
  -C "$root" -cpf "$backup/db.pg17.cold.tar" db
tar -tf "$backup/paperless-files.cold.tar" > "$backup/files-list.private.txt"
tar -tf "$backup/db.pg17.cold.tar" > "$backup/db-list.private.txt"
sha256sum "$backup/paperless.pg17.dump" "$backup/paperless-files.cold.tar" \
  "$backup/db.pg17.cold.tar" "$backup/images.tar" \
  > "$backup/SHA256SUMS"
sha256sum --check "$backup/SHA256SUMS"
```

GNU tar's POSIX ACL mode failed on this TrueNAS NFSv4 dataset during the Gitea
migration. `--no-acls` avoids that operation; `--xattrs-include='*'` requests
available native attributes, but **does not prove NFSv4 ACL fidelity**.
Record the native ACLs and use a ZFS snapshot/replication or another verified
ACL-preserving method for the recovery checkpoint. When the approved plan
includes an isolated restore, check native ACLs, numeric owners, modes, file
content, app access and DB readability. Record any skipped test before the
switch. Do not roll back the *whole* shared `SSD/Containers` dataset: it
contains other services. An archive listing and hashes prove only
readability/integrity. If a command fails **before** `old down`, inspect and
restart the original containers. After `old down` removes them, stop for manual
review of path state before recreating the old model. If the DB directory has
already moved, restore the PG17 path first; never start PG17 on PG18 files.

## Restore into a fresh PG18 cluster

The original PG17 directory must remain intact. Use a timestamped sibling so
the original bind source can be restored for rollback. Confirm targets are
ordinary paths on the expected dataset and do not already exist before moving.

```bash
stamp=$(date -u +%Y%m%dT%H%M%SZ)
old_db="$root/db.pg17-$stamp"
test ! -e "$old_db"
mv "$root/db" "$old_db"
mkdir "$root/db" "$root/db/18" "$root/db/18/docker"
chown 999:999 "$root/db" "$root/db/18" "$root/db/18/docker"
chmod 700 "$root/db" "$root/db/18" "$root/db/18/docker"
test "$(stat -c '%u:%g:%a' "$root/db")" = 999:999:700
test "$(stat -c '%u:%g:%a' "$root/db/18")" = 999:999:700
test "$(stat -c '%u:%g:%a' "$root/db/18/docker")" = 999:999:700
probe_pg18_storage "$root/db" # same function; new empty tree only
new up -d db
wait_db_ready
new exec -T db pg_restore --exit-on-error --clean --if-exists --create \
  -U paperless -d postgres < "$backup/paperless.pg17.dump"
new exec -T db psql -X -w -v ON_ERROR_STOP=1 -U paperless -d paperless \
  -c 'SHOW server_version;' -c 'SHOW data_directory;' -c 'ANALYZE;'
```

Require version 18.6, data directory `/var/lib/postgresql/18/docker`, the same
schema/object/row counts, roles, extension set and expected encoding/collation.
Check logs for collation warnings; follow the [Paperless collation guidance](https://docs.paperless-ngx.com/troubleshooting/#postgresql-warns-about-a-collation-version-mismatch)
with review before reindexing. Do not treat a healthy `pg_isready` alone as a
successful restore.

## Application acceptance and Portainer adoption

Keep clients and ingestion blocked while starting the unchanged app and other
unchanged services. Check `new ps` and bounded logs for all five services.
Confirm the app's effective engine remains PostgreSQL and points to `db`.
Sign in with an existing account and compare users/settings, permissions,
mail rules and workflows. Compare document count (currently zero), search and
media paths; for any actual documents, inspect originals, downloads,
thumbnails and the `document_sanity_checker`. Use an approved disposable
document to prove upload, OCR, search and download, then remove it. Verify Tika
and Gotenberg with a disposable Office file if that integration is used. Check
Redis-backed worker and scheduler health, logs and pending tasks. Finally,
recreate DB and webserver containers once and repeat the checks to prove the
new mount persists. Keep the observed production OCR/integration results
explicit; a local synthetic database rehearsal does not prove them.

```bash
new up -d
new ps
new logs --tail=100 db webserver broker tika gotenberg
new exec -T webserver document_sanity_checker
# After first acceptance, with ingestion still blocked:
new stop webserver
new up -d --force-recreate db
wait_db_ready
new up -d --force-recreate webserver
```

Keep PR #22 unmerged until the controlled live migration, application checks,
and separate merge approval. After merging, reconcile Portainer stack 136 to
the accepted `main` commit using the same private environment/project/volumes.
Confirm the deployed Git commit, image IDs, DB parent mount, PG18 data path,
health and restart counts before resuming Git polling. Do not leave a CLI
deployment and Portainer polling competing over the stack. Retain PG17 data,
the cold restore set, image archives and settings through the agreed rollback
window.

## Rollback

Before normal writers resume, stop the new stack and restore **both** the
original PG17 database directory and matching cold app/Redis files. Do not
point PostgreSQL 17 at PG18 files. Preserve failed PG18 state for diagnosis.
Use the saved old Compose, environment and image-ID override, without pulling:

```bash
new down                         # no -v
failed_db="$root/db.pg18-failed-$stamp"
test ! -e "$failed_db"
mv "$root/db" "$failed_db"
mv "$old_db" "$root/db"
for item in data media consume export redis; do
  test ! -e "$root/$item.pg18-failed-$stamp"
  mv "$root/$item" "$root/$item.pg18-failed-$stamp"
done
tar --same-owner --no-acls --xattrs --xattrs-include='*' --numeric-owner \
  -C "$root" -xpf "$backup/paperless-files.cold.tar"
```

At this point restore native NFSv4 ACLs from the approved checkpoint and
compare each restored path with its saved ACL, owner and mode report. Stop if
any differ; do not start the app on a content-only tar restore. A ZFS clone or
replication restore must target **only Paperless paths**, never the shared
`SSD/Containers` parent dataset. Continue only after an operator records the
native ACL and file-content check as passed:

```bash
read -r -p 'Type PAPERLESS_ACLS_VERIFIED after native ACL/content comparison: ' acl_gate
test "$acl_gate" = PAPERLESS_ACLS_VERIFIED
docker --host unix:///var/run/docker.sock image load -i "$backup/images.tar"
docker --host unix:///var/run/docker.sock compose -p paperless-ngx \
  --env-file "$backup/settings.env" \
  -f "$backup/compose.pg17.yaml" -f "$backup/images.pg17.yaml" \
  up -d --pull never db
wait_db_ready
docker --host unix:///var/run/docker.sock compose -p paperless-ngx \
  --env-file "$backup/settings.env" \
  -f "$backup/compose.pg17.yaml" -f "$backup/images.pg17.yaml" \
  up -d --pull never
```

Recheck the original counts, app login, documents/metadata and worker behavior
before reopening ingress. Restore the previous Portainer Git reference and
settings before polling resumes. Once normal writes run on PG18, the old PG17
copy is stale: a later rollback would lose those writes and requires a new
reconciliation plan.

## Evidence and limits

A disposable Docker Desktop database test with the exact PG17.11 and PG18.6
digests created a synthetic row on 17, restored a custom dump to 18,
confirmed `18/docker` persistence after DB recreation, and re-opened the
untouched 17 volume for rollback. A second no-published-port, internal-network
test used the exact Paperless 3.3.0 and Redis 7.4.11 pins. It booted Paperless
on PG17 with a generated admin, authenticated through the HTTP API, consumed a
synthetic image through the Redis-backed worker and checked OCR text, restored
its DB to PG18, authenticated and downloaded the document, then recreated the
DB and app containers and checked persistence. This does not test TrueNAS ACLs,
the actual backup/restore, Portainer adoption, production login, OCR quality, mail,
Tika/Gotenberg, Traefik or real document/media integrity. Those remain live
acceptance gates.

References: [official PostgreSQL image PGDATA and volume changes](https://github.com/docker-library/docs/blob/master/postgres/README.md#pgdata),
[PostgreSQL 18 backup and restore](https://www.postgresql.org/docs/18/backup.html),
[Paperless administration and backups](https://docs.paperless-ngx.com/administration/).
