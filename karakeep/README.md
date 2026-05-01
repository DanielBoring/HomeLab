# Karakeep

Karakeep is a self-hosted bookmark and read-later manager. You save a URL, and Karakeep fetches the page content, takes a screenshot via headless Chrome, and stores everything locally — no third-party sync service involved. It supports full-text search (powered by Meilisearch), AI-assisted automatic tagging (optional, via OpenAI), lists, highlights, and a browser extension for one-click saving.

**When to use it:** You want a private alternative to Pocket, Instapaper, or Raindrop.io where your reading list and saved content never leave your own infrastructure.

## Architecture

```
Browser / Extension
        │
        ▼
   Traefik (HTTPS, lan-only)
        │
        ▼
   karakeep :3000          ← Next.js web app + API
        │
        ├──► meilisearch :7700   ← full-text search index
        └──► chrome :9222        ← headless Chromium for screenshots & content fetch
```

All three containers share an internal `karakeep` bridge network. Only `karakeep` is attached to the `traefik` network — `chrome` and `meilisearch` have no external exposure.

Data is persisted to two bind-mounted directories on the host:
- `/mnt/SSD/Containers/karakeep/data` — bookmarks, attachments, user data
- `/mnt/SSD/Containers/karakeep/meilisearch` — search index

## Prerequisites

Create the host directories before first run:

```bash
mkdir -p /mnt/SSD/Containers/karakeep/data
mkdir -p /mnt/SSD/Containers/karakeep/meilisearch
```

The `traefik` external network must exist (deploy Traefik first).

## Quick Start

```bash
cp example.env .env
# Edit .env — fill in secrets and domain
docker compose up -d
```

Access at `https://<KARAKEEP_DOMAIN>`. Create your account on first visit.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `KARAKEEP_VERSION` | yes | Image tag — `release` for latest stable, or pin e.g. `0.10.0` |
| `KARAKEEP_DOMAIN` | yes | Domain Traefik routes to this service |
| `NEXTAUTH_SECRET` | yes | Random secret for session signing — `openssl rand -base64 36` |
| `MEILISEARCH_MASTER_KEY` | yes | Master key for Meilisearch — `openssl rand -base64 36` |
| `OPENAI_API_KEY` | no | Enables AI automatic tagging on saved bookmarks |

## Updates

**Pinned version** — bump `KARAKEEP_VERSION` in `.env`, then:
```bash
docker compose pull && docker compose up -d
```

**Rolling `release` tag**:
```bash
docker compose up --pull always -d
```

## Browser Extension

Karakeep has a browser extension for Chrome/Firefox that lets you save the current page with one click. Find it in the Karakeep web UI under Settings → Browser Extension.
