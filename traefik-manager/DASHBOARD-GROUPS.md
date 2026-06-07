# Traefik Manager Dashboard Groups

Traefik Manager does not currently read `traefik.manager.*` Docker labels for dashboard grouping. The dashboard groups routes by built-in keyword matching, then saves manual route overrides in `/app/config/dashboard.yml`.

This folder keeps that grouping intent in source control and generates the live `dashboard.yml` from the current Traefik Manager route IDs.

## Files

- `dashboard-groups.json` is the canonical grouping policy. It uses route display names such as `grafana`, `pmox1`, or `nextcloud-dav` so it is stable across provider-specific route IDs.
- `sync-dashboard-groups.py` reads live routes from Traefik Manager and writes only the supported `dashboard.yml` keys: `custom_groups` and `route_overrides`.

## Dry run

Use the exported dashboard list to confirm the grouping policy before touching the live config:

```powershell
python .\sync-dashboard-groups.py --routes-md C:\.git\traefik-manager-labels.md --dry-run --strict
```

Use the live API to preview route-ID-resolved output:

```powershell
python .\sync-dashboard-groups.py --api-url https://traefik-manager.virtuallyboring.com --dry-run
```

Add `--api-key <token>` if Traefik Manager API auth is enabled.

## Deploy

Run this on the host that can write Traefik Manager's config volume, or change `--output` to a staging path and copy it into place:

```bash
python sync-dashboard-groups.py \
  --api-url https://traefik-manager.virtuallyboring.com \
  --output /mnt/SSD/Containers/traefik-manager/config/dashboard.yml
```

Refresh the Traefik Manager dashboard after writing the file. The `Other` group should shrink to only intentionally skipped internal/no-op routes or newly discovered services that need to be added to `dashboard-groups.json`.
