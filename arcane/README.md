# Arcane

Self-hosted application management platform for homelabs. Provides a web UI for managing Docker containers, with a PostgreSQL backend.

[GitHub](https://github.com/getarcaneapp/arcane)

## Security Notice

This setup follows security best practices by using **environment variables** for secrets instead of hardcoding them in the compose file. This prevents sensitive credentials from being exposed in version control.

It does not hide settings from Docker administrators. Arcane mounts the Docker
socket with write access; anyone controlling Arcane can gain powerful host
control. Host port 3552 bypasses Traefik and must be restricted to trusted
clients. Read the [shared safeguards](../README.md#shared-operational-safeguards).

Commands below are for Bash on the Linux host, from `arcane/`. Before a new
deployment, create `/mnt/SSD/Containers/arcane` and
`/mnt/SSD/Containers/arcane-postgres`; grant the app path to the configured
`PUID:PGID` (default `3001:3001`) and leave database ownership to PostgreSQL.
Do not recursively change restored database ownership.

## Quick Start

### 1. Copy the environment template

```bash
cp .env.example .env
```

### 2. Generate secure secrets

Generate strong, random secrets for your installation:

```bash
# Generate ENCRYPTION_KEY (64 hex characters)
openssl rand -hex 32

# Generate JWT_SECRET (64 hex characters)
openssl rand -hex 32

# Generate database password (strong random password)
openssl rand -hex 32
```

### 3. Edit the .env file

Open the `.env` file in your preferred editor:

```bash
nano .env  # or vim, code, etc.
```

Replace the placeholder values with the secrets you generated above.
Set `DATABASE_URL` separately to the PostgreSQL connection URL using the same
user, password and database settings and host `postgres:5432`. A hex password is
URL-safe; otherwise URL-encode it in the URL, not in `POSTGRES_PASSWORD`.

### 4. Start the services

```bash
docker compose up -d
```

### 5. Verify everything is running

```bash
# Check container status
docker compose ps

# View logs
docker compose logs -f arcane

# Access the application
# Open http://localhost:3552 in your browser
```

## Environment Variables

### Required Secrets

These **MUST** be set in your `.env` file before starting:

| Variable | Description | How to Generate |
|----------|-------------|-----------------|
| `ENCRYPTION_KEY` | Used to encrypt sensitive data at rest | `openssl rand -hex 32` |
| `JWT_SECRET` | Used to sign authentication tokens | `openssl rand -hex 32` |
| `POSTGRES_PASSWORD` | Database initialization password | `openssl rand -hex 32` |
| `DATABASE_URL` | App connection URL; must match the database account | Construct privately with matching settings |

### Optional Configuration

These have sensible defaults but can be customized:

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_URL` | `http://localhost:3552` | External URL for the application |
| `PUID` | `3001` | User ID for file permissions |
| `PGID` | `3001` | Group ID for file permissions |
| `LOG_LEVEL` | `info` | Logging verbosity (debug, info, warn, error) |
| `LOG_JSON` | `false` | Output logs in JSON format |
| `POSTGRES_DB` | `arcane` | Database name |
| `POSTGRES_USER` | `arcane` | Database username |
| `OIDC_ENABLED` | `false` | Enable OpenID Connect authentication |

## Why Environment Variables?

### The Problem with Hardcoded Secrets

When secrets are hardcoded in configuration files:
- ❌ They become **permanently visible** in Git history
- ❌ They're **exposed to everyone** with repository access
- ❌ **Automated bots** scan GitHub and harvest credentials within minutes
- ❌ You can't use **different secrets** for different environments (dev/staging/prod)
- ❌ **Rotating secrets** requires code changes and redeployment

### The Solution: Environment Variables

Using environment variables for secrets provides:
- ✅ Secrets stored **outside version control**
- ✅ **Different secrets** per environment
- ✅ **Separate credential configuration** (rotation still needs the application's supported account/key procedure)
- ✅ **Access control** (only deployment systems need production secrets)
- ✅ **Industry standard** security practice

### How It Works

1. **`.env` file** (gitignored) - Contains your actual secrets
2. **`.env.example` file** (committed to git) - Template showing what variables are needed
3. **`compose.yaml`** uses `${VARIABLE}` syntax to read from `.env`
4. Docker Compose automatically loads variables when you run `docker compose up`

## Security Best Practices

### Critical Rules

1. **NEVER commit the .env file to version control**
   - It's already in `.gitignore` at the repository root
   - Always verify with: `git status` before committing
   - Double-check with: `git check-ignore arcane/.env` (should output: arcane/.env)

2. **Generate UNIQUE secrets for each installation**
   - Don't reuse secrets across different environments
   - Don't copy secrets from examples or tutorials
   - Use cryptographically secure random generators (like `openssl rand`)

3. **Use strong, random secrets**
   - Minimum 32 characters for passwords
   - 64 hex characters for encryption keys and JWT secrets
   - Never use dictionary words or predictable patterns

4. **Rotate credentials through supported procedures**
   - Revoke access after team member changes or suspected compromise.
   - Keep encryption keys backed up; do not replace them as routine rotation.
   - Update database accounts and matching connection settings together.

### File Permissions

Protect your `.env` file on Linux/Unix systems:

```bash
chmod 600 .env
```

This ensures only the file owner can read/write it.

### Backup Secrets Securely

If you need to backup your `.env` file, encrypt it first:

```bash
# Encrypt with GPG
gpg --symmetric --cipher-algo AES256 .env

# This creates .env.gpg - store it in a secure location
# NEVER commit .env.gpg to version control either!
```

To restore:

```bash
# Decrypt privately; preserve the current .env if decryption fails
(
  set -eu
  umask 077
  test ! -e .env.restored
  gpg --output .env.restored --decrypt .env.gpg
  docker compose --env-file .env.restored config --quiet
)
```

Review the restored settings privately before substituting them for the deployed
settings; do not print them. A valid Compose model does not verify credentials.

## Upgrading Security

This setup uses the **`.env` file pattern**, which is appropriate for:
- ✅ Local development
- ✅ Home lab environments
- ✅ Small teams with trusted members
- ✅ Non-critical/personal projects

For production environments or higher security requirements, consider:

### Docker Secrets (Docker Swarm)

Built into Docker Swarm mode, provides encrypted secret storage:

```bash
# Create a secret
echo "my_strong_password" | docker secret create postgres_password -

# Reference in compose.yaml
secrets:
  - postgres_password
```

### Cloud Secrets Managers

For enterprise or cloud deployments:
- **AWS Secrets Manager** - Automatic rotation, fine-grained access control
- **Azure Key Vault** - Integrated with Azure services
- **Google Secret Manager** - Integrated with GCP
- **HashiCorp Vault** - Multi-cloud, advanced features

## Troubleshooting

### Container Won't Start

Check if environment variables are loaded correctly:

```bash
# Validate without printing resolved secrets
docker compose config --quiet
```

### Database Connection Errors

Verify the DATABASE_URL is correctly constructed:

```bash
# Confirm the setting is assigned without printing it
grep -q '^DATABASE_URL=.' .env

# Should look like: postgresql://arcane:your_password@postgres:5432/arcane
```

Make sure the password doesn't contain special characters that need URL encoding. If it does, either:
- For a new installation, generate a URL-safe hex password
- URL-encode the special characters

For an existing database, do not generate a replacement merely to fix URL
encoding: keep the actual account password and encode it correctly in the URL.

### Permission Errors

The app path must grant access to the configured `PUID:PGID`, normally
`3001:3001`; this is not necessarily your interactive login user:

```bash
# Find your user ID
id -u

# Find your group ID
id -g

# Compare app directory permissions with the configured IDs.
# Do not change database data ownership to these IDs.
```

### Verifying .env is Ignored by Git

Always check before committing:

```bash
# This should output: arcane/.env
git check-ignore arcane/.env

# This should NOT list .env
git status
```

If `.env` appears in `git status`, check that:
1. `.gitignore` exists in the repository root
2. `.gitignore` contains `.env` on its own line
3. You haven't accidentally staged it with `git add -f`

## Maintenance

### Rotating Secrets

`POSTGRES_PASSWORD` initializes an **empty** PostgreSQL data directory; changing
it in `.env` does not change the existing role's password.

For database rotation, first take a consistent backup of both state paths and
the original keys/settings. Pause automation and app writes, use a trusted
interactive PostgreSQL administrator session to change the existing role's
password (the `psql` `\password` command avoids putting a password in a command
argument), then update **both** `POSTGRES_PASSWORD` and the password in
`DATABASE_URL`. Recreate the app with matching settings and verify authenticated
use before resuming automation. Plan rollback of both the role and settings;
do not delete the database to force initialization.

Do **not** replace `ENCRYPTION_KEY` without an Arcane-version-specific migration
that preserves/re-encrypts stored secrets. No such migration has been verified
for this un-inventoried image. Preserve the original key with every backup.
Changing `JWT_SECRET` may invalidate sessions; verify the deployed version's
supported procedure and plan a login interruption rather than rotating all keys
blindly.

PostgreSQL initialization behavior is documented by the
[official image](https://hub.docker.com/_/postgres) (checked 2026-10-13).

### Updating Arcane

Select a reviewed compatible exact release first; this stack still needs
running-image evidence before its floating references can be frozen safely.

```bash
# Pull only after reviewing image changes and migrations
docker compose pull

# Recreate containers with new image
docker compose up -d

# Check logs for any issues
docker compose logs -f arcane
```

### Backing Up Data

Your data is stored in:
- Arcane data: `/mnt/SSD/Containers/arcane`
- PostgreSQL data: `/mnt/SSD/Containers/arcane-postgres`

Use the [cold backup and isolated restore procedure](../README.md#backing-up-data)
for **both paths together**, with original Compose/image versions and encrypted
settings including `ENCRYPTION_KEY`, `JWT_SECRET`, and database credentials.
Stop both app and database before filesystem snapshots; a live PostgreSQL data
copy is not a backup. On recovery preserve the old tree, restore both paths with
numeric ownership and original settings, and start PostgreSQL before Arcane.
Verify login, projects and access to saved encrypted credentials before reopening.

## Additional Resources

- [Arcane GitHub Repository](https://github.com/getarcaneapp/arcane)
- [Docker Compose Environment Variables Documentation](https://docs.docker.com/compose/environment-variables/)
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [OpenSSL Random Generation](https://www.openssl.org/docs/man1.1.1/man1/rand.html)

## Support

For issues with:
- **Arcane application**: [GitHub Issues](https://github.com/getarcaneapp/arcane/issues)
- **This Docker Compose setup**: Check the HomeLab repository

## License

This configuration is part of the HomeLab project. See the repository LICENSE file for details.
