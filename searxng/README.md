# SearXNG

SearXNG is a privacy-respecting, self-hosted metasearch engine. It aggregates results from dozens of search engines (Google, Bing, DuckDuckGo, etc.) without tracking you, storing queries, or serving ads. Use it as your default browser search engine to get broad results without the surveillance.

## Why SearXNG

- No query logging, no user profiles, no ads
- Aggregates results from many sources simultaneously — better coverage than any single engine
- Fully configurable: choose which engines to enable, set safe-search level, customize the UI
- Redis-backed rate limiting prevents abuse without impacting normal use

## Architecture

```
Browser (LAN only)
      │ HTTPS
      ▼
  Traefik (lan-only middleware)
      │
      ▼
  searxng:8080 ──► External search engines (Google, Bing, DDG, …)
      │
      ▼
  redis:6379 (ephemeral cache + rate limiter, tmpfs — no persistence)
```

Both containers share the `searxng` internal network. Only the `searxng` container is also on the `traefik` network; Redis is never directly reachable from outside.

## Prerequisites

On the Docker host, create the config directory and place your `settings.yml` before running `docker compose up -d`:

```bash
mkdir -p /mnt/SSD/Containers/searxng/config

# Copy the template from this repo
cp config/settings.yml /mnt/SSD/Containers/searxng/config/settings.yml

# Generate a secret key and replace the placeholder
SECRET=$(openssl rand -hex 32)
sed -i "s/REPLACE_WITH_GENERATED_SECRET/$SECRET/" /mnt/SSD/Containers/searxng/config/settings.yml
```

> Do this **before** first run. Changing `secret_key` after launch invalidates all active sessions.

## Quick Start

```bash
cp example.env .env
# Edit .env — set SEARXNG_DOMAIN at minimum
nano .env

# Run the host prerequisite steps above, then:
docker compose up -d

# Verify both containers are healthy
docker compose ps
```

Visit `https://${SEARXNG_DOMAIN}` from the LAN (or VPN) — you should see the SearXNG search page.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SEARXNG_DOMAIN` | — | **Required.** Hostname Traefik routes to SearXNG (e.g. `searxng.yourdomain.com`) |
| `SEARXNG_PORT` | `8092` | Host port for direct access (Traefik is the primary entrypoint) |
| `TZ` | `America/New_York` | Container timezone |

## Configuration

SearXNG is configured via `/etc/searxng/settings.yml` inside the container, which is bind-mounted from `/mnt/SSD/Containers/searxng/config/` on the host. The committed `config/settings.yml` in this repo is a template — the actual file with the real `secret_key` lives only on the host.

Key settings:

| Setting | Default | Notes |
|---|---|---|
| `server.secret_key` | — | **Must be set.** Generate with `openssl rand -hex 32` |
| `server.limiter` | `true` | Rate limiting via Redis — keeps the instance healthy |
| `server.image_proxy` | `true` | Proxies result images through SearXNG (no external image requests from browser) |
| `search.safe_search` | `0` | `0` = off, `1` = moderate, `2` = strict |
| `search.autocomplete` | `duckduckgo` | Suggestion provider; set to `""` to disable |
| `ui.theme_args.simple_style` | `dark` | `dark` or `light` |

To add or remove search engines, add an `engines:` block to `settings.yml`. See the [SearXNG engine docs](https://docs.searxng.org/user/configured_engines.html) for available options.

## Updating

```bash
docker compose pull
docker compose up -d
```
