# OpenMetadata Local Setup

Local dev stack for LineageGuard. Runs OpenMetadata 1.9.1 via Docker Compose.

## Prerequisites

- Docker Desktop installed and running
- At least **6 GB of RAM** allocated to Docker (Settings → Resources)
- Ports 3306, 8080, 8585, 8586, 9200, 9300 must be free

## Windows: Fix vm.max_map_count (REQUIRED)

Elasticsearch 7.x requires `vm.max_map_count` ≥ 262144. Docker Desktop
on Windows (WSL2) defaults to 65530, causing ES to crash silently.

**Run this ONCE in a PowerShell terminal (admin not required):**

```powershell
wsl -d docker-desktop -u root sh -c "sysctl -w vm.max_map_count=262144"
```

To make it permanent across Docker Desktop restarts, create/edit the
file `C:\Users\<you>\.wslconfig`:

```ini
[wsl2]
kernelCommandLine = sysctl.vm.max_map_count=262144
```

Then restart Docker Desktop.

## Start the stack

```bash
docker compose up -d
```

First boot takes 3–5 minutes. The `execute-migrate-all` container runs
database migrations and then exits — this is normal.

## Check status

```bash
docker compose ps
```

Wait until `openmetadata_server` shows `healthy`. Watch logs:

```bash
docker compose logs -f openmetadata-server
```

Look for: `Started OpenMetadataApplication` in the output.

## Verify it works

Open **http://localhost:8585** in your browser.

| Field    | Value                       |
|----------|-----------------------------|
| Email    | admin@open-metadata.org     |
| Password | admin                       |

Airflow UI (ingestion worker): **http://localhost:8080** (admin / admin).

## Create a Personal Access Token (PAT)

1. Log in to http://localhost:8585
2. Click your profile icon (bottom-left) → **Settings**
3. Go to **Access Tokens** (under Integrations)
4. Click **Generate New Token**, name it `lineageguard`
5. Copy the token into your `.env` file:

```bash
cp .env.example .env
# Edit .env and paste the token after OPENMETADATA_TOKEN=
```

## Stop the stack

```bash
docker compose down
```

Data persists in named volumes. To wipe everything:

```bash
docker compose down -v
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| ES crashes silently (no logs) | Run the `vm.max_map_count` fix above. |
| Server won't start | Check Docker has ≥6 GB RAM. Run `docker compose logs openmetadata-server`. |
| Port conflict on 3306 | Stop local MySQL: `net stop MySQL`. |
| Port conflict on 8080 | Stop anything on 8080, or change the host port in `docker-compose.yml`. |
