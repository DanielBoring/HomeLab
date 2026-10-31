# ntopng

[ntopng](https://www.ntop.org/) is a network traffic analysis UI. **This stack
is limited:** it runs ntopng Community and Redis but does not configure a UniFi
NetFlow collector, nProbe, a Prometheus exporter, or a Prometheus scrape job.
Do not expect LAN-wide traffic visibility from deployment alone.

Images are frozen to inventoried builds. See the
[image update guide](../README.md#image-updates); a pull alone does not upgrade.

## Architecture

Traefik routes HTTPS to `ntopng:3000`; Redis is private on the owned `ntopng`
network. ntopng also joins external `traefik` and `monitoring`, but network
membership does not create a monitoring integration.

Compose currently publishes UDP 2055 without configuring a collector.
`NTOPNG_NETFLOW_PORT` changes that publication only; it does not enable ingestion.
No host-network packet capture or mirrored gateway interface is configured.
Any visible default interface traffic is container-local, not all LAN traffic.

Working NetFlow/IPFIX ingestion normally requires an upstream collector such as
nProbe and its supported transport into ntopng. Gateway export support,
licensing, editions and versions must be verified before adding that
architecture. See [ntop's nProbe integration guide](https://www.ntop.org/guides/ntopng/using_with_other_tools/nprobe.html)
(checked 2026-10-13). No exporter/dashboard setup is promised by this stack.

## Prerequisites and quick start

Run Bash commands on the Linux host from `ntopng/`. Deploy Traefik and Prometheus
first to create `traefik` and `monitoring`. Prepare
`/mnt/SSD/Containers/ntopng` and its `redis` directory. The images manage their
internal users; preserve existing ownership, rather than applying a blanket
`3001:3001` change to Redis.

```bash
mkdir -p /mnt/SSD/Containers/ntopng/redis
cp .env.example .env
# Set NTOPNG_DOMAIN and retain private settings outside Git
docker compose up -d
docker compose ps
docker compose logs --tail=100 ntopng
```

Access `https://<NTOPNG_DOMAIN>` from an allowed LAN client. This stack does not
pass `NTOPNG_ADMIN_USER`/`NTOPNG_ADMIN_PASSWORD` into ntopng.
Those obsolete template entries were removed; existing private settings using
them do not configure login. Complete the deployed
image's first-login password setup privately before granting other users access;
do not assume an arbitrary `.env` password works.

## Settings

| Setting | Default | Effect |
|---|---|---|
| `NTOPNG_DOMAIN` | Required | Traefik hostname |
| `NTOPNG_NETFLOW_PORT` | `2055` | Published UDP port only; no collector is configured |
| `TZ` | `America/New_York` | Container timezone |

Community mode and Redis address are fixed in Compose, not dotenv controls.
For the current limited stack, do not enable gateway export to this port.

## Operations and recovery

Preserve `/mnt/SSD/Containers/ntopng` **including Redis state**, original image
pins and private deployment settings. Redis contains persistent application
state here, not just a disposable cache. Stop both writers before a filesystem
backup; use the [shared cold backup/restore procedure](../README.md#backing-up-data).
An isolated same-version restore should retain login/settings/history; verify
those before accepting it.

Before updates, review the selected ntopng/Redis release and migration notes,
take a recoverable backup, then update reviewed pins before pulling/recreating.
For failed login or an empty interface view, inspect redacted logs and Redis
health first. An empty LAN view is expected without a configured ingestion
architecture, not proof of a network-health fault.
