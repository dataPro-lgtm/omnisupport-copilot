"""Week06 Dagster resource assembly."""

from __future__ import annotations

from pipelines.resources import (
    DataFactorySettings,
    MinIOResource,
    PostgresResource,
    ReportPathResource,
)


def build_week06_resources() -> dict:
    settings = DataFactorySettings.from_env()
    return {
        "week06_postgres": PostgresResource(database_url=settings.database_url),
        "week06_minio": MinIOResource(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
        ),
        "week06_reports": ReportPathResource(
            report_dir=str(settings.report_dir),
            backfill_dir=str(settings.backfill_dir),
            checks_dir=str(settings.checks_dir),
            run_evidence_dir=str(settings.run_evidence_dir),
        ),
    }
