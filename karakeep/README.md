# Karakeep

Karakeep is a self-hosted bookmark and read-later manager. You save a URL, and Karakeep fetches the page content, takes a screenshot via headless Chrome, and stores everything locally — no third-party sync service involved. It supports full-text search (powered by Meilisearch), AI-assisted automatic tagging (optional, via OpenAI), lists, highlights, and a browser extension for one-click saving.

**When to use it:** You want local control of saved content. Optional OpenAI
tagging sends selected content to an external provider; enabling its API key is
an explicit privacy/cost decision, not a purely local feature.

## Architecture

```text
Browser / Extension
        │
        ▼
   Traefik (HTTPS, lan-only)
        │
        ▼
   karakeep :3000          ← Next.js web app + API
        │
        ├──► meilisearch :7700   ← full-text search index
        └──► chrome.localhost :9222 ← headless Chromium for screenshots & content fetch
```

All three containers share an internal `karakeep` bridge network. Only `karakeep` is attached to the `traefik` network — `chrome` and `meilisearch` have no external exposure.

The Chrome sidecar is reachable through the `chrome.localhost` network alias. Chrome's DevTools endpoint rejects some requests whose `Host` header is a plain Docker service name such as `chrome`; using a `*.localhost` alias keeps the endpoint internal while satisfying Chrome's host validation.

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
cp .env.example .env
# Edit .env — fill in secrets and domain
docker compose up -d
```

Access at `https://<KARAKEEP_DOMAIN>`. Create your account on first visit.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `KARAKEEP_VERSION` | legacy selector | Currently interpolated image tag; this un-inventoried stack still needs verified literal pins |
| `KARAKEEP_DOMAIN` | yes | Domain Traefik routes to this service |
| `NEXTAUTH_SECRET` | yes | Random secret for session signing — `openssl rand -base64 36` |
| `MEILISEARCH_MASTER_KEY` | yes | Master key for Meilisearch — `openssl rand -base64 36` |
| `OPENAI_API_KEY` | no | Enables AI automatic tagging on saved bookmarks |

## Updates

Take a consistent backup and review the selected app/Meilisearch migrations
first. This stack still has a moving image selector; do not treat `release` as
a reviewed exact pin. Obtain deployed-image evidence, then replace the selector
with a verified literal tag/digest before a reproducible update.

After reviewing the image references:
```bash
docker compose pull && docker compose up -d
```

## Browser Extension

Karakeep has a browser extension for Chrome/Firefox that lets you save the current page with one click. Find it in the Karakeep web UI under Settings → Browser Extension.

## Operations and recovery

Run Linux/Bash examples from `karakeep/`. Inspect `docker compose ps` and recent
app/search/browser logs; verify login, an existing archived page and a search.
An app process alone does not prove browser captures or indexing work.

Pause clients/background jobs and stop all writers before preserving `data`
and `meilisearch` together, original images and encrypted settings/keys. Use the
[shared recovery procedure](../README.md#backing-up-data). Restore privately at
the same versions, verify bookmarks/attachments and search, then resume jobs.
Rebuild search only through the selected version's supported procedure, not by
deleting its volume as a routine fix. Keep external AI disabled during drills.
