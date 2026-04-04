# Prometheus PVE Exporter

Exports Proxmox VE cluster and node metrics to Prometheus via a `/pve` endpoint on port `9221`.

## Prerequisites

- `monitoring-stack` deployed first — the exporter joins the `monitoring` Docker network it creates
- A dedicated read-only user with an API token created in Proxmox

### Creating the Proxmox user and token

**1. Create the user**
- Datacenter → Permissions → Users → **Add**
- User: `prometheus`
- Realm: `Proxmox VE authentication server`
- Password doesn't matter (token auth won't use it)

**2. Assign the read-only role**
- Datacenter → Permissions → **Add → User Permission**
- Path: `/`
- User: `prometheus@pve`
- Role: `PVEAuditor`
- Propagate: checked

**3. Create the API token**
- Datacenter → Permissions → API Tokens → **Add**
- User: `prometheus@pve`
- Token ID: `monitoring` (this becomes `PVE_TOKEN_NAME`)
- **Uncheck "Privilege Separation"** — so the token inherits the user's PVEAuditor role
- Click Add → copy the secret UUID immediately, it is only shown once

> The token only needs to be created on one node — Proxmox syncs users and permissions across the cluster automatically.

## Quick Start

### 1. Copy the environment template

```bash
cp .env.example .env
```

### 2. Edit the .env file

```bash
nano .env
```

| Variable | Description |
|---|---|
| `PVE_USER` | Proxmox username — format `<user>@<realm>` |
| `PVE_TOKEN_NAME` | API token ID (e.g. `monitoring`) |
| `PVE_TOKEN_VALUE` | API token secret UUID |
| `PVE_VERIFY_SSL` | `true` to verify TLS cert, `false` for self-signed |

### 3. Deploy

```bash
docker compose up -d
```

### 4. Verify

```bash
# Check logs
docker logs prometheus-pve-exporter

# Query metrics (replace with your Proxmox host IP)
curl "http://localhost:9221/pve?target=<PROXMOX_IP>"
```

## Prometheus Scrape Config

Add to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'pve'
    static_configs:
      - targets:
          - <PROXMOX_IP>  # Proxmox host IP or hostname
    metrics_path: /pve
    params:
      module: [default]
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: prometheus-pve-exporter:9221
```

## Grafana Dashboard

Import the official dashboard from Grafana by ID:

| Dashboard | ID |
|---|---|
| Proxmox via Prometheus | [10347](https://grafana.com/grafana/dashboards/10347) |

## Maintenance

### Update image

```bash
docker compose pull
docker compose up -d
```

The exporter is stateless — no local data is stored, so no backup is needed.
