#!/usr/bin/env bash
# Backup only. No upgrade, restore, rename, source ownership change, or GitOps mutation.
# Run interactively as root on the reviewed TrueNAS host with one EMPTY private directory.
set -Eeuo pipefail
set -o noclobber
umask 077
export LC_ALL=C

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
[[ $# -eq 1 ]] || fail 'Usage: bash backup-gitea-pg17.sh /mnt/SSD/Containers/gitea-backup-TIMESTAMP'
backup=$1
root=/mnt/SSD/Containers/gitea
app=gitea
db=gitea-db
app_volume=gitea_gitea-data
db_volume=gitea_gitea-db
app_ref=docker.gitea.com/gitea@sha256:87a67ee09d3ae0d1df5fda5dcda3e2a1f9236a45b0a59025d6e00e46adc43bef
db_ref=postgres:17.11@sha256:2d2b8998d31037bf721cfdf764d76ba74171b4fab3431b7f72c27c56ddbdf9e3
D=(docker --host unix:///var/run/docker.sock)
d() { "${D[@]}" "$@"; }

[[ $(id -u) == 0 ]] || fail 'Run as root.'
[[ $(hostname) == TrueNAS ]] || fail 'Expected hostname TrueNAS.'
[[ -z ${DOCKER_HOST:-} ]] || fail 'Unset DOCKER_HOST and recheck the reviewed local context.'
[[ -z ${DOCKER_CONTEXT:-} || ${DOCKER_CONTEXT} == default ]] || fail 'Expected default Docker context.'
for cmd in docker realpath stat find findmnt df du awk tail tr tar sha256sum date sleep mkdir rmdir chmod cat; do
  command -v "$cmd" >/dev/null || fail "Required command missing: $cmd"
done
[[ $(docker context show) == default ]] || fail 'Expected Docker context default.'
[[ $(d info --format '{{.OSType}}') == linux ]] || fail 'Expected native Linux Docker engine.'
# The explicit Unix socket above prevents a remote/default-context override.
d compose version >/dev/null
for option in --acls --xattrs --numeric-owner --sparse --one-file-system; do
  [[ $(tar --help) == *"$option"* ]] || fail "GNU tar option unavailable: $option"
done

[[ $backup == /mnt/SSD/Containers/gitea-backup-* && ${backup%/*} == /mnt/SSD/Containers ]] || fail 'Backup must be a sibling gitea-backup-* directory.'
for path in "$root" "$root/data" "$root/db" "$backup"; do
  [[ -d $path && ! -L $path ]] || fail "Expected ordinary directory: $path"
  [[ $(realpath -e "$path") == "$path" ]] || fail "Symlink/alias detected: $path"
  read -r mount_target mount_source mount_type < <(findmnt -T "$path" -n -o TARGET,SOURCE,FSTYPE)
  [[ $mount_target == /mnt/SSD/Containers && $mount_source == SSD/Containers && $mount_type == zfs ]] || fail "Unexpected dataset/mount for $path"
done
[[ $(stat -c '%u:%g:%a' "$root") == 3001:3001:700 ]] || fail 'Unexpected Gitea root ownership/mode.'
[[ $(stat -c '%u:%g:%a' "$root/data") == 3001:3001:700 ]] || fail 'Unexpected app data ownership/mode.'
[[ $(stat -c '%u:%g:%a' "$root/db") == 999:999:700 ]] || fail 'Unexpected DB ownership/mode.'
[[ $(stat -c '%u:%a' "$backup") == 0:700 ]] || fail 'Backup directory must be root-owned mode 700.'
[[ -z $(find "$backup" -mindepth 1 -maxdepth 1 -print -quit) ]] || fail 'Backup directory is not empty; do not reuse it.'
[[ -z $(find "$root/data" "$root/db" -xdev -type l -print -quit) ]] || fail 'Nested symlink found; review external storage before backup.'
child_mounts=$(findmnt -rn -o TARGET | awk -v p="$root" '$0 == p || index($0,p"/") == 1')
[[ -z $child_mounts ]] || fail 'Source includes a mountpoint or child mount; use dataset-aware backup.'
[[ $(cat "$root/db/PG_VERSION") == 17 ]] || fail 'Expected PostgreSQL 17 data.'

for container in "$app" "$db"; do
  [[ $(d inspect --format '{{.State.Running}}' "$container") == true ]] || fail "Expected $container already running."
  [[ $(d inspect --format '{{.State.Paused}}' "$container") == false ]] || fail "Unexpected paused container: $container"
  [[ $(d inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "$container") == gitea ]] || fail 'Unexpected Compose project.'
  [[ $(d inspect --format '{{index .Config.Labels "com.docker.compose.service"}}' "$container") == "$container" ]] || fail 'Unexpected Compose service.'
done
[[ $(d inspect --format '{{.Config.Image}}' "$app") == "$app_ref" ]] || fail 'Gitea image reference changed.'
[[ $(d inspect --format '{{.Config.Image}}' "$db") == "$db_ref" ]] || fail 'PostgreSQL image reference changed.'
app_container=$(d inspect --format '{{.Id}}' "$app")
db_container=$(d inspect --format '{{.Id}}' "$db")
app_id=$(d inspect --format '{{.Image}}' "$app")
db_id=$(d inspect --format '{{.Image}}' "$db")
[[ $app_id == sha256:* && $db_id == sha256:* ]] || fail 'Invalid local image IDs.'
[[ $(d image inspect --format '{{.Id}}' "$app_ref") == "$app_id" ]] || fail 'App local image ID mismatch.'
[[ $(d image inspect --format '{{.Id}}' "$db_ref") == "$db_id" ]] || fail 'DB local image ID mismatch.'
[[ $(d inspect --format '{{range .Mounts}}{{if eq .Destination "/data"}}{{printf "%s|%s|%t" .Type .Name .RW}}{{end}}{{end}}' "$app") == "volume|$app_volume|true" ]] || fail 'Unexpected app mount.'
[[ $(d inspect --format '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{printf "%s|%s|%t" .Type .Name .RW}}{{end}}{{end}}' "$db") == "volume|$db_volume|true" ]] || fail 'Unexpected DB mount.'
for pair in "$app_volume:data" "$db_volume:db"; do
  volume=${pair%%:*}; suffix=${pair#*:}
  [[ $(d volume inspect --format '{{.Driver}}|{{index .Options "type"}}|{{index .Options "device"}}|{{index .Options "o"}}' "$volume") == "local|none|$root/$suffix|bind" ]] || fail 'Unexpected volume bind source/options.'
done
[[ $(d inspect --format '{{len .Mounts}}' "$app") == 1 && $(d inspect --format '{{len .Mounts}}' "$db") == 1 ]] || fail 'Additional storage mounts require review.'
version=$(d exec "$db" psql -X -w -At -v ON_ERROR_STOP=1 -U gitea -d gitea -c 'SHOW server_version_num;')
[[ $version =~ ^[0-9]+$ && $version -ge 170000 && $version -lt 180000 ]] || fail 'Expected running PG17 server.'
[[ $(d exec "$db" psql -X -w -At -v ON_ERROR_STOP=1 -U gitea -d gitea -c 'SHOW data_directory;') == /var/lib/postgresql/data ]] || fail 'Unexpected running PGDATA.'

source_bytes=$(du -s -B1 "$root/data" "$root/db" | awk '{sum+=$1} END {printf "%.0f",sum}')
image_bytes=$(d image inspect --format '{{.Size}}' "$app_id" "$db_id" | awk '{sum+=$1} END {printf "%.0f",sum}')
available_bytes=$(df -B1 --output=avail "$backup" | tail -n 1 | tr -d ' ')
required_bytes=$((2 * (source_bytes + image_bytes) + 1073741824))
[[ $available_bytes =~ ^[0-9]+$ && $available_bytes -ge $required_bytes ]] || fail 'Insufficient conservative free-space allowance.'
printf 'Preflight passed. This creates a SAME-POOL local backup, not protection against pool loss.\n'
printf 'Before continuing: Portainer Git polling/redeployment and image updaters for Gitea must be paused.\n'
printf 'Drain/stop external Actions jobs, mirrors and all other DB/file writers; keep them paused until completion.\n'
printf 'This stops Gitea, then PG17 briefly for cold archives, and restarts the same existing containers.\n'
[[ -t 0 ]] || fail 'Interactive confirmation is required; do not pipe this script into bash.'
read -r -p 'Type BACKUP to confirm GitOps is paused and this downtime is approved: ' approval
[[ $approval == BACKUP ]] || fail 'No downtime approval; no backup/stop action taken.'

mkdir "$backup/.backup-in-progress"
: > "$backup/errors.private.log"
chmod 600 "$backup/errors.private.log"
downtime_started=0

wait_db() {
  local i
  for ((i=0; i<60; i++)); do
    if d exec "$db" pg_isready -U gitea -d gitea >/dev/null 2>> "$backup/errors.private.log"; then return 0; fi
    sleep 2
  done
  return 1
}
resume_original_services() {
  printf 'Restoring the original running services...\n'
  [[ $(d inspect --format '{{.Id}}' "$db" 2>> "$backup/errors.private.log") == "$db_container" ]] || return 1
  [[ $(d inspect --format '{{.Image}}' "$db" 2>> "$backup/errors.private.log") == "$db_id" ]] || return 1
  [[ $(d inspect --format '{{.Id}}' "$app" 2>> "$backup/errors.private.log") == "$app_container" ]] || return 1
  [[ $(d inspect --format '{{.Image}}' "$app" 2>> "$backup/errors.private.log") == "$app_id" ]] || return 1
  if [[ $(d inspect --format '{{.State.Running}}' "$db" 2>> "$backup/errors.private.log") != true ]]; then
    d start "$db" >/dev/null 2>> "$backup/errors.private.log" || return 1
  fi
  wait_db || return 1
  if [[ $(d inspect --format '{{.State.Running}}' "$app" 2>> "$backup/errors.private.log") != true ]]; then
    d start "$app" >/dev/null 2>> "$backup/errors.private.log" || return 1
  fi
  local i
  for ((i=0; i<60; i++)); do
    if d exec "$app" curl -fsS http://localhost:3000/api/healthz >/dev/null 2>> "$backup/errors.private.log"; then
      downtime_started=0
      return 0
    fi
    sleep 2
  done
  return 1
}
on_exit() {
  local rc=$? recovery_rc=0
  trap - EXIT INT TERM
  set +e
  if (( downtime_started )); then
    resume_original_services
    recovery_rc=$?
  fi
  if (( recovery_rc != 0 )); then
    rc=1
    printf 'ERROR: automatic restart/readiness failed. Keep GitOps paused; inspect original containers.\n' >&2
  fi
  local status=INCOMPLETE
  if (( rc == 0 )); then status=COMPLETE_ARCHIVE_CHECKS_ONLY; fi
  printf 'status=%s\nended_utc=%s\nexit_status=%s\n' "$status" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$rc" > "$backup/finished.txt" || rc=1
  if (( rc != 0 )); then
    printf 'FAILED: incomplete backup retained privately at %s; do not treat it as verified.\n' "$backup" >&2
  fi
  rmdir "$backup/.backup-in-progress"
  exit "$rc"
}
trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

printf 'started_utc=%s\nhost=TrueNAS\nproject=gitea\napp_image_id=%s\ndb_image_id=%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$app_id" "$db_id" > "$backup/manifest.txt"
d inspect "$app" "$db" > "$backup/containers.private.json" 2>> "$backup/errors.private.log"
d volume inspect "$app_volume" "$db_volume" > "$backup/volumes.private.json" 2>> "$backup/errors.private.log"
d image inspect "$app_id" "$db_id" > "$backup/images.private.json" 2>> "$backup/errors.private.log"
printf 'services:\n  gitea:\n    image: %s\n  gitea-db:\n    image: %s\n' "$app_id" "$db_id" > "$backup/images.pg17.yaml"
printf 'Saving original local images before downtime...\n'
d image save "$app_id" "$db_id" > "$backup/images.tar" 2>> "$backup/errors.private.log"
test -s "$backup/images.tar"

printf 'Stopping Gitea; native logical backup follows...\n'
downtime_started=1
d stop --time 120 "$app" >/dev/null 2>> "$backup/errors.private.log"
[[ $(d inspect --format '{{.State.Running}}' "$app") == false ]] || fail 'Gitea did not stop.'
clients=$(d exec "$db" psql -X -w -At -v ON_ERROR_STOP=1 -U gitea -d gitea -c "SELECT count(*) FROM pg_stat_activity WHERE backend_type='client backend' AND pid<>pg_backend_pid();" 2>> "$backup/errors.private.log")
[[ $clients == 0 ]] || fail 'Other database clients remain. Backup aborted; original services will restart.'
d exec "$db" pg_dump --format=custom --create -U gitea -d gitea > "$backup/gitea.dump" 2>> "$backup/errors.private.log"
d exec "$db" pg_dumpall --globals-only -U gitea > "$backup/globals.private.sql" 2>> "$backup/errors.private.log"
test -s "$backup/gitea.dump"
test -s "$backup/globals.private.sql"
clients=$(d exec "$db" psql -X -w -At -v ON_ERROR_STOP=1 -U gitea -d gitea -c "SELECT count(*) FROM pg_stat_activity WHERE backend_type='client backend' AND pid<>pg_backend_pid();" 2>> "$backup/errors.private.log")
[[ $clients == 0 ]] || fail 'Another database client appeared; stop and investigate.'
printf 'Stopping PG17 for cold DB and app filesystem archives...\n'
d stop --time 120 "$db" >/dev/null 2>> "$backup/errors.private.log"
[[ $(d inspect --format '{{.State.Running}}' "$db") == false ]] || fail 'Database did not stop.'
[[ $(d inspect --format '{{.State.ExitCode}}' "$db") == 0 ]] || fail 'Database shutdown was not clean; cold archive aborted.'
[[ $(d inspect --format '{{.State.OOMKilled}}' "$db") == false ]] || fail 'Database was OOM-killed; cold archive aborted.'
tar --acls --xattrs --xattrs-include='*' --numeric-owner --sparse --one-file-system \
  -C "$root" -cpf - db > "$backup/db.pg17.cold.tar" 2>> "$backup/errors.private.log"
tar --acls --xattrs --xattrs-include='*' --numeric-owner --sparse --one-file-system \
  -C "$root" -cpf - data > "$backup/gitea-data.cold.tar" 2>> "$backup/errors.private.log"
test -s "$backup/db.pg17.cold.tar"
test -s "$backup/gitea-data.cold.tar"
resume_original_services || fail 'Original service restart/readiness failed.'

# Validation and hashing happen AFTER the original services are available again.
printf 'Original services resumed. Validating archive formats and hashing private artifacts...\n'
d exec -i "$db" pg_restore --list < "$backup/gitea.dump" > "$backup/dump-contents.private.txt" 2>> "$backup/errors.private.log"
tar -tf "$backup/db.pg17.cold.tar" > "$backup/db-archive-contents.private.txt" 2>> "$backup/errors.private.log"
tar -tf "$backup/gitea-data.cold.tar" > "$backup/app-archive-contents.private.txt" 2>> "$backup/errors.private.log"
tar -tf "$backup/images.tar" > "$backup/image-archive-contents.private.txt" 2>> "$backup/errors.private.log"
printf 'archives_checked_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$backup/manifest.txt"
(
  cd "$backup"
  sha256sum manifest.txt containers.private.json volumes.private.json images.private.json \
    images.pg17.yaml images.tar gitea.dump globals.private.sql db.pg17.cold.tar gitea-data.cold.tar \
    dump-contents.private.txt db-archive-contents.private.txt app-archive-contents.private.txt \
    image-archive-contents.private.txt > SHA256SUMS
  sha256sum --check --status SHA256SUMS
)
# All artifacts are root-private via umask; the directory remains root-owned mode 700.
[[ -z $(find "$backup" -maxdepth 1 -type f ! -perm 0600 -print -quit) ]] || fail 'Unexpected backup file permissions.'
printf 'SUCCESS: backup artifacts and checksums created at %s\n' "$backup"
printf 'Archive listing/checksums are NOT a restore test. Keep GitOps paused for the next reviewed step.\n'
printf 'Private Portainer Compose/settings/overrides export is still required for a complete rollback plan.\n'
