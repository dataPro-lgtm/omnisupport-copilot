# Week04 Catalog Runtime Plan v1

## Configuration Contract

The canonical environment contract lives in `infra/env/.env.example` and is loaded by `pipelines/lakehouse/settings.py`.

Required keys:
- `ICEBERG_CATALOG_NAME`
- `ICEBERG_CATALOG_TYPE`
- `ICEBERG_CATALOG_URI`
- `ICEBERG_WAREHOUSE`
- `ICEBERG_NAMESPACE_BRONZE`
- `ICEBERG_NAMESPACE_SILVER`
- `ICEBERG_FILE_IO`
- `ICEBERG_S3_ENDPOINT`
- `ICEBERG_S3_ACCESS_KEY_ID`
- `ICEBERG_S3_SECRET_ACCESS_KEY`
- `ICEBERG_S3_REGION`
- `ICEBERG_S3_PATH_STYLE_ACCESS`
- `WEEK04_DATA_RELEASE_ID`
- `WEEK04_INGEST_BATCH_ID`
- `WEEK04_REPORT_DIR`

## Runtime Components

| Component | Role |
|---|---|
| PostgreSQL | Source tables and PyIceberg SQL Catalog metadata. |
| MinIO | Iceberg warehouse bucket and data/metadata files. |
| Devbox | Student CLI runtime with PyIceberg and PyArrow installed. |
| Dagster | Thin asset wrapper, not the primary Week04 runtime. |

## Validation Commands

```bash
docker compose --env-file infra/env/.env.local -f infra/docker-compose.yml up -d --build postgres minio minio_init
```

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python -m pipelines.lakehouse.settings --check
```

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python -m pipelines.lakehouse.catalog --smoke
```

## Known Limits

The Week04 devbox owns real PyIceberg execution. The Dagster container can show Lakehouse assets, but it is not treated as the source of truth for Iceberg writes until the project owns a Dagster image with the same dependencies.
