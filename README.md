# Week 7 Project: [Your Project Name]

## What it does

<!-- Describe your pipeline in 1-2 sentences. What data does it fetch? Where does it store the results? -->

## Architecture

```text
[Your API] ──► pipeline.py ──► Pydantic validation ──► Postgres INSERT (your schema)
                                                     ──► Blob Storage (raw JSON)
```

## Run locally

```bash
# 1. Populate .env from Azure Key Vault
cp .env.example .env
echo "POSTGRES_URL=$(az keyvault secret show --vault-name kv-hyf-data --name postgres-url --query value -o tsv)" >> .env
echo "AZURE_STORAGE_CONNECTION_STRING=$(az keyvault secret show --vault-name kv-hyf-data --name storage-connection-string --query value -o tsv)" >> .env
# Set your personal schema (replace alice with your GitHub handle):
echo "DB_SCHEMA=dev_alice" >> .env

# 2. Install dependencies
uv sync

# 3. Run directly (without Docker)
uv run python -m src.pipeline

# 4. Or build and run with Docker
docker build -t my-pipeline .
docker run --env-file .env my-pipeline
```

## Run tests

```bash
uv run pytest tests/ -v
```

## Deploy to Azure

```bash
# Build for linux/amd64 (required by Azure Container Apps) and push to ACR
docker build --platform linux/amd64 -t hyfregistry.azurecr.io/my-pipeline:1.0 .
docker push hyfregistry.azurecr.io/my-pipeline:1.0

# Create Container App Job (runs daily at 06:00 UTC)
az containerapp job create \
  --name my-pipeline-job \
  --resource-group rg-hyf-data \
  --environment env-hyf-data \
  --image hyfregistry.azurecr.io/my-pipeline:1.0 \
  --registry-server hyfregistry.azurecr.io \
  --trigger-type Schedule \
  --cron-expression "0 6 * * *" \
  --replica-timeout 300 \
  --replica-retry-limit 0 \
  --env-vars \
    POSTGRES_URL="$(az keyvault secret show --vault-name kv-hyf-data --name postgres-url --query value -o tsv)" \
    AZURE_STORAGE_CONNECTION_STRING="$(az keyvault secret show --vault-name kv-hyf-data --name storage-connection-string --query value -o tsv)" \
    DB_SCHEMA=dev_alice \
    LOG_LEVEL=INFO

# Trigger a manual run for testing (without waiting for the schedule)
az containerapp job start --name my-pipeline-job --resource-group rg-hyf-data
```

## Enable ACR push from CI (optional)

The `push-to-acr` job in `.github/workflows/ci.yml` is commented out by default.
To enable it, add two secrets in your repo's **Settings → Secrets and variables → Actions**:

| Secret name | Value |
|-------------|-------|
| `ACR_USERNAME` | `hyfregistry` |
| `ACR_PASSWORD` | Ask your teacher for the ACR password |

Then uncomment the `push-to-acr` job in `ci.yml`. Every push to `main` will build
and push the image automatically.

## Install psql

`psql` is the Postgres command-line client used to verify results. Install it once:

**macOS**
```bash
brew install libpq
echo 'export PATH="/opt/homebrew/opt/libpq/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

**Linux (Debian/Ubuntu)**
```bash
sudo apt-get install -y postgresql-client
```

**Windows**
Download and run the installer from [postgresql.org/download/windows](https://www.postgresql.org/download/windows/). The installer includes `psql`. After installing, open a new terminal and verify with `psql --version`.

## Verify results

```bash
# Check job execution
az containerapp job execution list --name my-pipeline-job --resource-group rg-hyf-data --output table

# Check Postgres (replace dev_alice with your schema, <your_table> with your table name)
psql "$POSTGRES_URL" -c "SELECT COUNT(*) FROM dev_alice.<your_table>;"

# Check Blob Storage
az storage blob list --account-name hyfstoragedev --container-name raw --prefix pipeline/ --output table
```

## Clean up

```bash
az containerapp job delete --name my-pipeline-job --resource-group rg-hyf-data --yes
```
