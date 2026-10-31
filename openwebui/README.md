# Open WebUI

Open WebUI running as a Docker container on TrueNAS, connected to a remote Ollama instance.

Images in `compose.yaml` are frozen to the inventoried builds. See the [image update guide](../README.md#image-updates); `docker compose pull` alone does not upgrade them.

## Architecture

```text
TrueNAS (Docker)               Gaming PC / Remote Host
┌──────────────────────────┐   ┌─────────────────────┐
│  Traefik → Open WebUI    │──▶│  Ollama  :11434     │
│  :8080 (internal)        │   │  (OLLAMA_BASE_URL)  │
└──────────────────────────┘   └─────────────────────┘
        ▲
  https://${OPENWEBUI_DOMAIN}
```

## Prerequisites

Deploy Traefik first. Run Linux host commands from `openwebui/`; Ollama setup
below runs on its separate host. This route does not include `lan-only`, so
require application authentication and verify ingress restrictions.

Create the data directory before deploying:

```bash
mkdir -p /mnt/SSD/Containers/openwebui
```

## Quick Start

```bash
cp .env.example .env
# Edit .env — set OLLAMA_BASE_URL and OPENWEBUI_DOMAIN
docker compose up -d
```

Then open `https://<OPENWEBUI_DOMAIN>`. DNS must resolve the domain to Traefik (`10.0.5.5`) before the UI is reachable.

## Configuration

| Variable          | Description                        | Example                                  |
|-------------------|------------------------------------|------------------------------------------|
| `OLLAMA_BASE_URL` | URL of the remote Ollama instance  | `http://<ollama-host>:11434`             |
| `OPENWEBUI_DOMAIN`| Hostname Traefik routes to the UI  | `openwebui.yourdomain.com`               |

## Ollama Host Requirements

The Ollama instance must be reachable from the TrueNAS host over the network.

### 1. Listen on all interfaces

By default Ollama only binds to `127.0.0.1`. Set `OLLAMA_HOST` to make it accept remote connections:

**Windows — system environment variable (persistent):**
```powershell
[System.Environment]::SetEnvironmentVariable("OLLAMA_HOST", "0.0.0.0", "Machine")
# Restart the Ollama service/app after setting this
```

**Windows — per-session (temporary):**
```powershell
$env:OLLAMA_HOST = "0.0.0.0"
ollama serve
```

**Linux/macOS:**
```bash
OLLAMA_HOST=0.0.0.0 ollama serve
```

### 2. Open port 11434 in the firewall

Ollama's API is not authenticated by this stack. Restrict access to the specific
trusted Docker host's source IP; do not open it to all clients or the internet.
Replace the placeholder below before running it.

**Windows Defender (PowerShell, run as Administrator on the Ollama host):**
```powershell
New-NetFirewallRule -DisplayName "Ollama from TrueNAS" -Direction Inbound -Protocol TCP -LocalPort 11434 -RemoteAddress '<TrueNAS-source-IP>' -Action Allow
```

### 3. Verify connectivity

From the TrueNAS host:
```bash
curl http://<ollama-host>:11434/api/tags
```

A JSON response listing available models confirms the connection is working.

## Changing the Ollama URL After Deployment

You can update the Ollama connection without restarting the container via the UI:

**Settings > Admin Settings > Connections > Ollama API**

Changes take effect immediately.

## Recovery and updates

Check `docker compose ps`, recent `open-webui` logs and authenticated UI/model
listing; test a harmless request only after the backend is reachable. Stop
writers before preserving the entire backend-data path (database, uploads,
configuration and any stored keys), original settings and image pin using the
[shared recovery procedure](../README.md#backing-up-data). Restore privately at
the same version with original ownership and verify users/history/uploads.
Ollama model storage is on the remote host and needs a separate recovery plan.
Review schema migrations before changing the image; retain pre-update state.
