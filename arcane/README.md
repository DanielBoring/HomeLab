# Arcane Docker Compose Setup

This directory contains the Docker Compose configuration for running [Arcane](https://github.com/getarcaneapp/arcane), a self-hosted application management platform for homelabs.

## Security Notice

This setup follows security best practices by using **environment variables** for secrets instead of hardcoding them in the compose file. This prevents sensitive credentials from being exposed in version control.

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
openssl rand -base64 32
```

### 3. Edit the .env file

Open the `.env` file in your preferred editor:

```bash
nano .env  # or vim, code, etc.
```

Replace the placeholder values with the secrets you generated above.

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
| `POSTGRES_PASSWORD` | Database password | `openssl rand -base64 32` |

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
- ✅ **Easy rotation** (just update `.env` and restart)
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

4. **Rotate secrets regularly**
   - Change passwords quarterly
   - Especially after team member changes
   - After any suspected security incident

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
# Decrypt the backup
gpg --decrypt .env.gpg > .env

# Verify contents
cat .env

# Start services
docker compose up -d
```

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
# View the final configuration with variables substituted
docker compose config

# Look for empty or ${VARIABLE} values which indicate missing .env variables
```

### Database Connection Errors

Verify the DATABASE_URL is correctly constructed:

```bash
# Check the DATABASE_URL in your .env file
grep DATABASE_URL .env

# Should look like: postgresql://arcane:your_password@postgres:5432/arcane
```

Make sure the password doesn't contain special characters that need URL encoding. If it does, either:
- Generate a new password without special characters
- URL-encode the special characters

### Permission Errors

The PUID/PGID should match your user:

```bash
# Find your user ID
id -u

# Find your group ID
id -g

# Update .env if needed
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

To change your secrets (recommended quarterly):

1. Generate new secrets:
   ```bash
   openssl rand -hex 32  # For ENCRYPTION_KEY
   openssl rand -hex 32  # For JWT_SECRET
   openssl rand -base64 32  # For POSTGRES_PASSWORD
   ```

2. Update `.env` file with new values

3. Restart services:
   ```bash
   docker compose down
   docker compose up -d --force-recreate
   ```

4. Verify application works:
   ```bash
   docker compose logs -f
   ```

### Updating Arcane

To update to the latest version:

```bash
# Pull the latest image
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

Back these up regularly:

```bash
# Stop containers first
docker compose down

# Backup (example using tar)
tar -czf arcane-backup-$(date +%Y%m%d).tar.gz \
  /mnt/SSD/Containers/arcane \
  /mnt/SSD/Containers/arcane-postgres

# Restart containers
docker compose up -d
```

Don't forget to backup your `.env` file securely (encrypted)!

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
