# Open WebUI

Open WebUI runs on TrueNAS and connects to LM Studio on a Windows PC over the LAN.

Images in `compose.yaml` are frozen to the inventoried builds. See the [image update guide](../README.md#image-updates); `docker compose pull` alone does not upgrade them.

## Architecture

```text
TrueNAS (Docker)               Windows PC
┌──────────────────────────┐   ┌────────────────────────┐
│  Traefik → Open WebUI    │──▶│  LM Studio /v1         │
│  :8080 (internal)        │   │  (LM_STUDIO_BASE_URL)  │
└──────────────────────────┘   └────────────────────────┘
        ▲
  https://${OPENWEBUI_DOMAIN}
```

## Prerequisites

Deploy Traefik first. Run Docker Compose commands from `openwebui/` on TrueNAS.
Require application authentication and verify ingress restrictions for the
Traefik route.

Create the data directory before deploying:

```bash
mkdir -p /mnt/SSD/Containers/openwebui
```

## Quick Start

```bash
test -f .env || cp .env.example .env
# Edit .env with the LM Studio base URL, optional API token, and Open WebUI domain.
docker compose up -d
```

Then open `https://<OPENWEBUI_DOMAIN>`. DNS must resolve the domain to Traefik (`10.0.5.5`) before the UI is reachable.

## Configuration

| Variable | Description | Example |
| --- | --- | --- |
| `LM_STUDIO_BASE_URL` | LM Studio's OpenAI-compatible base URL, including `/v1` | `http://<windows-lan-ip>:1234/v1` |
| `LM_STUDIO_API_KEY` | LM Studio API token when **Require Authentication** is enabled | Leave blank when authentication is disabled |
| `OPENWEBUI_DOMAIN` | Hostname Traefik routes to the UI | `openwebui.yourdomain.com` |

## LM Studio Host Requirements

In LM Studio, enable **Serve on Local Network** in the local server settings and
start the server. Use the Windows PC's LAN IP and the configured LM Studio port
in `LM_STUDIO_BASE_URL`. A container on TrueNAS reaches the Windows PC over the
LAN. Its own `localhost` points back to the container.

If Windows Firewall blocks the connection, allow the LM Studio port from the
TrueNAS source IP. To test reachability from TrueNAS, substitute the same URL
you set in `LM_STUDIO_BASE_URL` and append `/models`.

```bash
curl -fsS 'http://<windows-lan-ip>:1234/v1/models'
```

A JSON model list confirms that TrueNAS can reach the API. If LM Studio requires
authentication, supply the token as a bearer token for the test.

## Switching an Existing Deployment

Use the updated `compose.yaml` and replace `OLLAMA_BASE_URL` in the TrueNAS
deployment's `.env` with `LM_STUDIO_BASE_URL`, then run `docker compose up -d`.

Open WebUI can give saved connection settings precedence over Compose values.
Under **Admin Settings → Connections**, verify that the LM Studio URL is set as
an OpenAI-compatible connection and that the Ollama connection is disabled.
Save those settings if the previous connection is still active, then select an
LM Studio model and send a test message.

## Recovery and updates

Check `docker compose ps`, recent `open-webui` logs and authenticated UI/model
listing; test a harmless request only after the backend is reachable. Stop
writers before preserving the entire backend-data path (database, uploads,
configuration and any stored keys), original settings and image pin using the
[shared recovery procedure](../README.md#backing-up-data). Restore privately at
the same version with original ownership and verify users/history/uploads.
LM Studio model storage is on the Windows PC and needs a separate recovery plan.
Review schema migrations before changing the image; retain pre-update state.
