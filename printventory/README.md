# Printventory on TrueNAS (Portainer)

[Printventory](https://printventory.com/) ([source](https://github.com/TechJeeper/Printventory))
is a self-hosted library manager for 3D-printable files (STL, 3MF, OBJ, STEP
and more). It scans your model folders, renders thumbnails, and gives you
search, tagging, collections, print history, filament tracking (including
Spoolman integration), and "open in slicer" shortcuts. Printventory started as
an Electron desktop app. This stack runs its **Server Mode** Docker image, so
any browser on the LAN can browse the library.

Images in `compose.yaml` are frozen to the inventoried builds. See the [image update guide](../README.md#image-updates); `docker compose pull` alone does not upgrade them.

## Why and when to use it

Use it if your models are spread across years of downloads and project folders
and you want them searchable and previewable without opening each file. It
indexes files where they already are. It reads your existing folder structure
and doesn't need its own copy of the files.

It's not a print-farm controller. For printer control and print archiving, see
[Bambu Buddy](../bambuddy/README.md). Printventory answers "which model is this
and where is it?"; Bambu Buddy answers "what is the printer doing?"

## Architecture

```text
Browser on LAN
    |
    v HTTPS
Traefik (10.0.5.5)  -- secure-headers + lan-only
    |
    v shared Docker bridge network "traefik"
Printventory (port 5000, no host port)
    |-- /root/.config/printventory  <- /mnt/SSD/Containers/printventory/data (SQLite DB, thumbnails, settings)
    `-- /mnt/models (read-only)     <- ${PRINTVENTORY_MODELS_PATH} (your model library)
```

- **Traefik terminates TLS.** Leave Printventory's built-in HTTPS / Let's
  Encrypt settings **off**, and don't publish ports 80/443/5000 on the host.
- **No host port** is published. The UI is reachable only through Traefik.
- **Storage:** a single SQLite database (`better-sqlite3`). There's no separate
  database container.

## Security considerations (read before deploying)

- **Upstream Server Mode has no login.** Anyone who can reach the URL gets
  full access. That's why the router uses `lan-only@file`. Don't expose this
  service to the internet without adding an auth layer in front of it, such as
  an SSO/forward-auth middleware.
- **The MCP endpoint (`/mcp`) is always enabled.** Upstream says any client
  that can reach it "can read and change library data". It sits behind the same
  Traefik route, so the LAN allowlist covers it too.
- **The model library is mounted read-only (`:ro`).** Printventory can delete,
  flatten and reorganize files ("Organize Library", delete model, 3MF to STL).
  With `:ro`, those features fail rather than changing your library. If you
  want them, remove `:ro` from the `printventory-models` mount and make sure
  you have snapshots of that dataset first.
- **The container runs as root.** The upstream image keeps its data under
  `/root/.config` and doesn't support `PUID`/`PGID`. The read-only mount limits
  what it can touch on the model share.

## Prerequisites

- The Traefik stack is running and has created the external `traefik` network.
- A LAN DNS record for `printventory.virtuallyboring.com` points to Traefik
  (`10.0.5.5`).
- Your model library lives on a TrueNAS dataset reachable from the Docker host.
  Set its path in `PRINTVENTORY_MODELS_PATH`.
- About 4 GB of RAM available for the container on large libraries. 2 GB is
  enough for small ones. Thumbnail generation is CPU-heavy on first scan.

Create the data directory before the first deployment:

```sh
mkdir -p /mnt/SSD/Containers/printventory/data
```

The model directory must already exist. The named volume binds to it and
Docker fails to start the container if it doesn't.

## Quick start

1. Copy `.env.example` to `.env` (CLI), or enter its values as Portainer stack
   variables. Don't commit `.env`.
2. Set `PRINTVENTORY_MODELS_PATH` to the host path of your model library.
3. Validate the stack from the repo root:

   ```sh
   docker compose --env-file printventory/.env -f printventory/compose.yaml config --quiet
   ```

4. Deploy:
   - **Portainer:** select the `TrueNAS.virtuallyboring.com` environment and
     create a Git repository stack with Compose path
     `printventory/compose.yaml`. Supply the variables from `.env.example`.
   - **CLI:** `docker compose -f printventory/compose.yaml up -d`
5. Watch the first start. Electron takes up to a minute to come up:

   ```sh
   docker logs -f printventory
   ```

6. Open `https://printventory.virtuallyboring.com`. On first start,
   `/mnt/models` is seeded as the STL Home folder and a scan begins. Add
   subfolders or change the scan interval (default 60 min) under Settings.
7. Confirm the `printventory` router is green in the Traefik dashboard.

**Use container paths in the UI.** Inside Printventory, your library is at
`/mnt/models/...`, not the TrueNAS host path.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `PRINTVENTORY_DOMAIN` | — (required) | Hostname for the Traefik router. |
| `PRINTVENTORY_MODELS_PATH` | — (required) | Host path of your model library, bind-mounted read-only at `/mnt/models`. |
| `PRINTVENTORY_STL_HOME_EXCLUDE` | empty | Comma-separated container paths to skip during scans, e.g. `/mnt/models/cache`. Applied only while the exclude list in the UI is empty. |
| `PRINTVENTORY_MEM_LIMIT` | `4g` | Container memory cap. The app's V8 heap auto-sizes from it. |
| `PRINTVENTORY_GPU` | `swiftshader` | Thumbnail WebGL backend: `swiftshader` (CPU), `auto`, or `nvidia`. `nvidia` also needs `gpus: all` and `NVIDIA_DRIVER_CAPABILITIES=graphics,compute,utility`. |
| `PRINTVENTORY_PREVIEW_3MF_WORKER_MEMORY_MB` | `512` | Memory budget per 3MF preview worker. Keep it well below `PRINTVENTORY_MEM_LIMIT`. |
| `PRINTVENTORY_PREVIEW_3MF_MAX_FILE_SIZE_MB` | `200` | Skips or limits previews of very large 3MF files. |
| `TZ` | `America/New_York` | Container timezone. |

The compose file sets these fixed values:

| Variable | Value | Why |
|---|---|---|
| `STL_HOME` | `/mnt/models` | Seeds the library folder list. It applies only while the list in the UI is empty, so later UI edits stick. |
| `DISPLAY`, `PUPPETEER_*`, `DCONF_DISABLE`, `GIO_*`, `DBUS_FATAL_WARNINGS` | upstream values | Run Electron/Chromium headless without noisy D-Bus errors. |

Upstream also supports these variables, which this stack doesn't use:

- `PRINTVENTORY_ENV_OVERRIDES_SETTINGS=1` re-applies env vars over UI settings
  on every start.
- `PRINTVENTORY_PORT` changes the listen port. If you set it, update the
  Traefik service port to match.
- `PRINTVENTORY_DB_PATH` overrides the database location.
- `PRINTVENTORY_MAX_OLD_SPACE_MB` sets the V8 heap size directly.
- `PRINTVENTORY_TLS_*` sets up in-container HTTPS. That's not needed because
  Traefik handles TLS.

## Troubleshooting

- **502 from Traefik:** the container may still be starting (Electron is slow
  on first boot). Check `docker ps` for `healthy`, and check that the container
  is on the `traefik` network.
- **Browser shows "WebSocket connection failed", or the container restarts
  during scans:** it ran out of memory. Raise `PRINTVENTORY_MEM_LIMIT`, or lower
  `PRINTVENTORY_PREVIEW_3MF_WORKER_MEMORY_MB`.
- **Logs show `OOM error in V8: Zone Allocation failed`:** raise
  `PRINTVENTORY_MEM_LIMIT`. The heap scales from it.
- **Chromium sandbox errors at startup:** `no-new-privileges` can block
  Chromium's setuid sandbox helper. Electron as root normally runs unsandboxed,
  so this shouldn't come up. If it does, check the logs before relaxing
  `security_opt`.
- **Delete/organize actions fail:** this is expected while the library is
  mounted `:ro`. See Security considerations.

## Backup and upgrades

Everything that matters is in `/mnt/SSD/Containers/printventory/data`: the
SQLite DB, generated thumbnails, and settings. Your model files stay on their
own dataset. Back them up separately.

Stop the app before a consistent SQLite/files backup and follow the
[shared recovery procedure](../README.md#backing-up-data), retaining original
pins/settings. Restore to a fresh destination with original ownership (the
image uses root), confirm collections/thumbnails and model paths, and retain the
old state until accepted. Checksums alone do not prove recovery. Do not drop the
read-only model mount during a restore drill.

To upgrade, read the [release notes](https://github.com/TechJeeper/Printventory/releases)
and take a backup. Then review an image-update PR or update both the tag and
digest in `compose.yaml` before redeploying the stack. Existing
`PRINTVENTORY_VERSION` values in `.env` or Portainer no longer select the image
and can be removed during your next planned settings update.
Don't use the in-app updater with this Git-managed stack.
