# Unpoller

Polls a UniFi network controller and exposes metrics to Prometheus via a `/metrics` endpoint on port `9130`.

## Prerequisites

- `monitoring-stack` deployed first — Unpoller joins the `monitoring` Docker network it creates
- A read-only local user named `unifipoller` created on the UniFi controller

### Creating the UniFi user

In your UniFi controller:

1. Go to **Settings → Admins & Users → Add Admin**
2. Set role to **Read Only**
3. Uncheck **"Use a Ubiquiti account"** — create a local account
4. Set the username to `unifipoller` and choose a strong password
5. Save, then add that password to your `.env` file

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
| `UNIFI_URL` | Controller URL — no `:8443` for UDM/UDM-Pro/UXG |
| `UNIFI_USER` | Read-only controller username |
| `UNIFI_PASS` | Controller password |

### 3. Deploy

```bash
docker compose up -d
```

### 4. Verify

```bash
# Check logs — should show successful poll
docker logs unpoller

# Confirm metrics endpoint is responding
curl http://localhost:9130/metrics
```

## Controller URL Format

| Device | URL format |
|---|---|
| UDM, UDM-Pro, UXG, recent CloudKey | `https://192.168.x.x` |
| Legacy CloudKey, self-hosted controller | `https://192.168.x.x:8443` |

## Grafana Dashboards

Import the official Unpoller dashboards from Grafana by ID:

| Dashboard | ID |
|---|---|
| UniFi Insights - Sites | [11315](https://grafana.com/grafana/dashboards/11315) |
| UniFi Insights - USG | [11312](https://grafana.com/grafana/dashboards/11312) |
| UniFi Insights - UAP | [11314](https://grafana.com/grafana/dashboards/11314) |
| UniFi Insights - USW | [11313](https://grafana.com/grafana/dashboards/11313) |

## Optional Metrics

These are disabled by default to reduce load. Enable in `compose.yaml` by setting to `true`:

| Variable | Description |
|---|---|
| `UP_UNIFI_DEFAULT_SAVE_DPI` | Deep packet inspection data |
| `UP_UNIFI_DEFAULT_SAVE_EVENTS` | Controller events |
| `UP_UNIFI_DEFAULT_SAVE_ALARMS` | Controller alarms |
| `UP_UNIFI_DEFAULT_SAVE_ANOMALIES` | Network anomalies |
| `UP_UNIFI_DEFAULT_SAVE_IDS` | Intrusion detection |

## Maintenance

### Update image

```bash
docker compose pull
docker compose up -d
```

Unpoller is stateless — no data is stored locally, so no backup is needed.
