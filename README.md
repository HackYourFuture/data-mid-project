# Week 7 Project: [Your Project Name]

## What it does

<!-- Describe your pipeline in 1-2 sentences. What data does it fetch? Where does it store the results? -->

## Architecture

```text
[Your API] ──► pipeline.py ──► Pydantic validation ──► Postgres INSERT
                                                     ──► Blob Storage (raw JSON)
```

## Run locally

```bash
# 1. Populate .env from Azure Key Vault
cp .env.example .env
echo "POSTGRES_URL=$(az keyvault secret show --vault-name kv-hyf-data --name postgres-url --query value -o tsv)" >> .env
echo "AZURE_STORAGE_CONNECTION_STRING=$(az keyvault secret show --vault-name kv-hyf-data --name storage-connection-string --query value -o tsv)" >> .env

# 2. Build and run with Docker
docker build -t my-pipeline .
docker run --env-file .env my-pipeline
```

## Run tests

```bash
pip install pytest
pytest tests/ -v
```

## Deploy to Azure

```bash
# Push image to ACR
docker tag my-pipeline hyfregistry.azurecr.io/my-pipeline:1.0
docker push hyfregistry.azurecr.io/my-pipeline:1.0

# Create Container App Job
az containerapp job create \
  --name my-pipeline-job \
  --resource-group rg-hyf-data \
  --environment env-hyf-data \
  --image hyfregistry.azurecr.io/my-pipeline:1.0 \
  --registry-server hyfregistry.azurecr.io \
  --trigger-type Manual \
  --replica-timeout 300 \
  --replica-retry-limit 0 \
  --env-vars \
    POSTGRES_URL="$(az keyvault secret show --vault-name kv-hyf-data --name postgres-url --query value -o tsv)" \
    AZURE_STORAGE_CONNECTION_STRING="$(az keyvault secret show --vault-name kv-hyf-data --name storage-connection-string --query value -o tsv)" \
    LOG_LEVEL=INFO

# Start the job
az containerapp job start --name my-pipeline-job --resource-group rg-hyf-data
```

## Verify results

```bash
# Check job execution
az containerapp job execution list --name my-pipeline-job --resource-group rg-hyf-data --output table

# Check Postgres
psql "$POSTGRES_URL" -c "SELECT COUNT(*) FROM your_table_name;"  # replace with your table name

# Check Blob Storage
az storage blob list --account-name hyfstoragedev --container-name raw --prefix pipeline/ --output table
```

## Clean up

```bash
az containerapp job delete --name my-pipeline-job --resource-group rg-hyf-data --yes
```
