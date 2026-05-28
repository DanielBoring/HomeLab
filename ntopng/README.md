# ntopng

ntopng is a web-based network traffic analysis and monitoring tool by [ntop](https://www.ntop.org/). It provides real-time and historical visibility into who is talking to whom on your network, how much bandwidth each host or application is consuming, and what protocols are in use — down to Layer 7 application detection via the nDPI engine (450+ protocols).

**Why you'd use it over UniFi's built-in stats:** UniFi reports aggregate bandwidth per device; ntopng shows individual flows, application breakdown (e.g., "which app on which host used 4 GB last night"), and historical trend data. It complements UniFi-Poller's device-health metrics with deep per-flow visibility.

## Architecture

```
UDM SE
  │ NetFlow UDP → host port 2055
  ▼
ntopng (Docker)
  │ REST API
  ▼
ntopng-exporter ──→ Prometheus (monitoring network) ──→ Grafana
  │
ntopng-redis (session state, internal ntopng network)
```

Traffic ingestion uses **NetFlow from the UDM SE** — the gateway sees all LAN traffic and exports summarized flow records to ntopng. This means ntopng sees every device conversation without needing raw packet access or `--network=host`.

The `ntopng-exporter` sidecar queries ntopng's REST API and exposes metrics in Prometheus format. Prometheus scrapes it on the shared `monitoring` network, making ntopng data available in Grafana alongside your existing dashboards.

## Prerequisites

### 1. Create host directories (on TrueNAS)

```bash
mkdir -p /mnt/SSD/Containers/ntopng/redis
chown -R 3001:3001 /mnt/SSD/Containers/ntopng
```

### 2. Ensure external networks exist

Both `traefik` and `monitoring` must already exist. Deploy `traefik/` and `prometheus/` first if you haven't already.

## Quick Start

```bash
cp example.env .env
# Edit .env — set NTOPNG_DOMAIN and NTOPNG_ADMIN_PASSWORD
docker compose up -d
```

## Configure NetFlow on UDM SE

1. Log in to UniFi Network Controller at `10.0.1.1`
2. Navigate to **Settings → System → Advanced**
3. Under **NetFlow**, enable the toggle
4. Set **NetFlow Host** = TrueNAS IP address
5. Set **NetFlow Port** = `2055` (or the value of `NTOPNG_NETFLOW_PORT`)
6. Save

After saving, open ntopng at `https://${NTOPNG_DOMAIN}` and navigate to **Interfaces**. A NetFlow collector interface should appear within 1–2 minutes once the UDM SE begins exporting.

## Configure ntopng NetFlow Interface (first run)

ntopng does not auto-detect the UDP port — you configure it once via the web UI:

1. Log in with the admin credentials from `.env`
2. Go to **Admin → Interfaces → Add Interface**
3. Select **Flow Collector** → **NetFlow/IPFIX**
4. Set the listen port to `2055`
5. Save and apply

## Add Grafana Dashboard

Import community dashboard **[#20071](https://grafana.com/grafana/dashboards/20071-ntopng-exporter/)** (ntopng-exporter):

1. Grafana → **Dashboards → Import**
2. Enter ID `20071`, click **Load**
3. Select the `prometheus` datasource
4. Save into a new **Network** folder

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `NTOPNG_DOMAIN` | — | Traefik hostname for the web UI |
| `NTOPNG_ADMIN_USER` | `admin` | ntopng admin username |
| `NTOPNG_ADMIN_PASSWORD` | — | ntopng admin password (also used by exporter) |
| `NTOPNG_NETFLOW_PORT` | `2055` | Host UDP port that receives NetFlow from UDM SE |
| `TZ` | `America/New_York` | Container timezone |

## Prometheus Scraping

`ntopng-exporter` listens on port `9244` inside the `monitoring` network. Prometheus is configured to scrape it via the `ntopng` job in `prometheus/prometheus.yml`.

After deploying ntopng, restart Prometheus to pick up the new scrape job:

```bash
cd ../prometheus && docker compose restart prometheus
```

Verify under **Prometheus → Status → Targets** that the `ntopng` job shows **UP**.

## Notes

- **Community Edition** is free and sufficient for this setup. The `--community` flag in the command activates it; no license file is needed.
- **Data persistence:** ntopng stores RRD timeseries and configuration in `/mnt/SSD/Containers/ntopng`. Redis persists session state in `/mnt/SSD/Containers/ntopng/redis`.
- **ClickHouse (future):** If you later want SQL-level historical analysis or longer retention, ntopng Enterprise L supports ClickHouse as a timeseries backend, which Grafana can query directly. The community + Prometheus-exporter path covers most use cases without the additional infrastructure.
