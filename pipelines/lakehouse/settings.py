"""Week04 Lakehouse runtime settings.

The Week04 student path runs inside the Docker devbox.  Settings are read from
environment variables so the same code can run on a local compose network or in
an instructor-scale environment without hard-coded endpoints.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class LakehouseSettings:
    catalog_name: str = "omni"
    catalog_type: str = "sql"
    catalog_uri: str = "postgresql+psycopg2://omni:omnipass@postgres:5432/omnisupport"
    warehouse: str = "s3://omni-lakehouse/warehouse"
    bronze_namespace: str = "bronze"
    silver_namespace: str = "silver"
    file_io: str = "pyiceberg.io.pyarrow.PyArrowFileIO"
    s3_endpoint: str = "http://minio:9000"
    s3_access_key_id: str = "minioadmin"
    s3_secret_access_key: str = "minioadmin"
    s3_region: str = "us-east-1"
    s3_path_style_access: str = "true"
    data_release_id: str = "week04-dev-local"
    ingest_batch_id: str = "week04-smoke"
    report_dir: str = "reports/week04"
    database_url: str = "postgresql://omni:omnipass@postgres:5432/omnisupport"

    @classmethod
    def from_env(cls) -> "LakehouseSettings":
        return cls(
            catalog_name=os.getenv("ICEBERG_CATALOG_NAME", cls.catalog_name),
            catalog_type=os.getenv("ICEBERG_CATALOG_TYPE", cls.catalog_type),
            catalog_uri=os.getenv("ICEBERG_CATALOG_URI", cls.catalog_uri),
            warehouse=os.getenv("ICEBERG_WAREHOUSE", cls.warehouse),
            bronze_namespace=os.getenv("ICEBERG_NAMESPACE_BRONZE", cls.bronze_namespace),
            silver_namespace=os.getenv("ICEBERG_NAMESPACE_SILVER", cls.silver_namespace),
            file_io=os.getenv("ICEBERG_FILE_IO", cls.file_io),
            s3_endpoint=os.getenv("ICEBERG_S3_ENDPOINT", cls.s3_endpoint),
            s3_access_key_id=os.getenv("ICEBERG_S3_ACCESS_KEY_ID", cls.s3_access_key_id),
            s3_secret_access_key=os.getenv("ICEBERG_S3_SECRET_ACCESS_KEY", cls.s3_secret_access_key),
            s3_region=os.getenv("ICEBERG_S3_REGION", cls.s3_region),
            s3_path_style_access=os.getenv(
                "ICEBERG_S3_PATH_STYLE_ACCESS",
                cls.s3_path_style_access,
            ),
            data_release_id=os.getenv("WEEK04_DATA_RELEASE_ID", cls.data_release_id),
            ingest_batch_id=os.getenv("WEEK04_INGEST_BATCH_ID", cls.ingest_batch_id),
            report_dir=os.getenv("WEEK04_REPORT_DIR", cls.report_dir),
            database_url=os.getenv("DATABASE_URL", cls.database_url),
        )

    @property
    def report_path(self) -> Path:
        path = Path(self.report_dir)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path

    @property
    def warehouse_bucket(self) -> str:
        parsed = urlparse(self.warehouse)
        if parsed.scheme != "s3" or not parsed.netloc:
            return ""
        return parsed.netloc

    def as_catalog_properties(self) -> dict[str, str]:
        return {
            "type": self.catalog_type,
            "uri": self.catalog_uri,
            "warehouse": self.warehouse,
            "py-io-impl": self.file_io,
            "s3.endpoint": self.s3_endpoint,
            "s3.access-key-id": self.s3_access_key_id,
            "s3.secret-access-key": self.s3_secret_access_key,
            "s3.region": self.s3_region,
            "s3.path-style-access": self.s3_path_style_access,
        }

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.catalog_type != "sql":
            errors.append("ICEBERG_CATALOG_TYPE must be 'sql' for Week04.")
        if not self.catalog_uri.startswith("postgresql"):
            errors.append("ICEBERG_CATALOG_URI must point at PostgreSQL SQL Catalog.")
        if not self.warehouse.startswith("s3://"):
            errors.append("ICEBERG_WAREHOUSE must be an s3:// MinIO warehouse URI.")
        if not self.warehouse_bucket:
            errors.append("ICEBERG_WAREHOUSE must include the MinIO bucket name.")
        if not self.s3_endpoint:
            errors.append("ICEBERG_S3_ENDPOINT is required.")
        if not self.database_url.startswith("postgresql"):
            errors.append("DATABASE_URL must be a PostgreSQL DSN.")
        return errors

    def to_safe_dict(self) -> dict[str, str]:
        payload = asdict(self)
        payload["s3_secret_access_key"] = "***"
        payload["catalog_uri"] = _redact_password(self.catalog_uri)
        payload["database_url"] = _redact_password(self.database_url)
        return payload


def _redact_password(value: str) -> str:
    if "@" not in value or ":" not in value:
        return value
    prefix, suffix = value.rsplit("@", 1)
    if ":" not in prefix:
        return value
    user_part = prefix.split("//", 1)
    if len(user_part) != 2:
        return value
    scheme, auth = user_part
    user = auth.split(":", 1)[0]
    return f"{scheme}//{user}:***@{suffix}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Week04 Lakehouse settings self-check")
    parser.add_argument("--check", action="store_true", help="validate required settings")
    parser.add_argument("--print-config", action="store_true", help="print redacted JSON config")
    args = parser.parse_args()

    settings = LakehouseSettings.from_env()
    if args.print_config:
        print(json.dumps(settings.to_safe_dict(), indent=2, ensure_ascii=False))

    errors = settings.validate()
    if args.check or not args.print_config:
        if errors:
            print(json.dumps({"ok": False, "errors": errors}, indent=2, ensure_ascii=False))
            return 1
        print(json.dumps({"ok": True, "warehouse_bucket": settings.warehouse_bucket}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
