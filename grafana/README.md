# Grafana

Dashboard and visualization layer for the homelab. Connects to Prometheus (and optionally Loki) over the shared `monitoring` Docker network. The Prometheus datasource is provisioned automatically — no manual setup needed after first login.

Images in `compose.yaml` are frozen to the inventoried builds. See the [image update guide](../README.md#image-updates); `docker compose pull` alone does not upgrade them.

## Prerequisites

**Deploy the [prometheus](../prometheus/) stack first** — it creates the `monitoring` Docker network this stack requires.
Traefik must already own `traefik`. Run Linux/Bash commands from `grafana/`.

Create the persistent storage directories and set ownership:

```bash
mkdir -p /mnt/SSD/Containers/grafana/provisioning/{datasources,dashboards}
chown -R 3001:3001 /mnt/SSD/Containers/grafana
cp provisioning/datasources/prometheus.yml provisioning/datasources/loki.yml \
  /mnt/SSD/Containers/grafana/provisioning/datasources/
```

Directory creation/ownership above is for a fresh installation. Back up and
compare existing provisioning before replacing files; preserve restored owners.
These host copies are what the read-only container mount reads. Updating the
repository alone does not update a previously copied host configuration.

## Quick Start

```bash
cp .env.example .env
nano .env  # set GRAFANA_ADMIN_PASSWORD and GRAFANA_DOMAIN
docker compose up -d
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `GRAFANA_ADMIN_USER` | No | `admin` | Admin username |
| `GRAFANA_ADMIN_PASSWORD` | Yes for new setup | — | Initial admin password; changing it does not rotate an existing account |
| `GRAFANA_DOMAIN` | Yes | — | Hostname Traefik routes to Grafana |

Grafana UI: `https://<GRAFANA_DOMAIN>` (via Traefik, LAN only)

## Datasources

The Prometheus datasource is provisioned via [provisioning/datasources/prometheus.yml](provisioning/datasources/prometheus.yml) — it points to `http://prometheus:9090` and is set as the default. No manual configuration required.

The Loki datasource is provisioned from the copied
[loki.yml](provisioning/datasources/loki.yml) at `http://loki:3100`.
Deploy Loki before expecting log queries to succeed; provisioning a URL does
not install the backend.

## Dashboards

The **Active Directory Status** dashboard can be imported in Grafana from
[`dashboards/active-directory.json`](dashboards/active-directory.json).
It combines AD1 and AD2 metrics from Prometheus with selected Windows Event Viewer
warnings, errors, authentication failures, and account lockouts from Loki. A
reading guide and each panel's information tooltip explain healthy, warning, and
problem conditions.

Import dashboards by ID from [grafana.com/grafana/dashboards](https://grafana.com/grafana/dashboards). Useful starting points:

| Dashboard | ID | Purpose |
|---|---|---|
| Node Exporter Full | 1860 | Host system metrics |
| UniFi Poller | 11315 | UniFi network stats |
| Traefik | 17346 | Traefik request metrics |
| Proxmox | 10347 | Proxmox cluster metrics |

## Plugins

The following plugins are pre-installed at startup:

| Plugin | Purpose |
|---|---|
| `grafana-clock-panel` | Clock/time display panels |
| `natel-discrete-panel` | Discrete state timeline panels |
| `grafana-piechart-panel` | Pie chart panels |

## Storage

| Data | Path |
|---|---|
| Dashboards, users, settings | `/mnt/SSD/Containers/grafana` |

## Maintenance

```bash
# Update image
docker compose pull && docker compose up -d

```

Before updates review plugin compatibility and take a consistent backup. Stop
Grafana before preserving its SQLite data, installed provisioning and original
image/settings using the [shared recovery procedure](../README.md#backing-up-data).
Restore the whole data/config set with UID 3001 access, verify existing users,
dashboards and datasource queries, then reopen access. The initial admin
environment variables do not reset an existing account.
