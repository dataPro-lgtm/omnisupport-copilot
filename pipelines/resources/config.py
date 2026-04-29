"""Environment-backed runtime configuration for Week06 data factory."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def resolve_project_root() -> Path:
    configured = os.getenv("WEEK06_PROJECT_ROOT")
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.exists():
            return candidate

    cwd = Path.cwd()
    for candidate in (cwd, *cwd.parents):
        if (candidate / "pyproject.toml").exists() and (candidate / "contracts").exists():
            return candidate

    return Path(__file__).resolve().parents[2]


def _resolve_path(project_root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else project_root / path


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int | None) -> int | None:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return int(raw)


@dataclass(frozen=True)
class DataFactorySettings:
    project_root: Path
    database_url: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    manifest_dir: Path
    ticket_seed_path: Path
    report_dir: Path
    partition_start_date: str
    default_partition: str
    ingest_dry_run: bool
    ingest_limit: int | None
    data_release_id: str
    operator: str
    week04_report_path: Path
    week05_run_results_path: Path
    metric_registry_path: Path
    git_sha: str
    trace_id: str

    @classmethod
    def from_env(cls) -> "DataFactorySettings":
        project_root = resolve_project_root()
        return cls(
            project_root=project_root,
            database_url=os.getenv(
                "DATABASE_URL",
                "postgresql://omni:omnipass@postgres:5432/omnisupport",
            ),
            minio_endpoint=os.getenv("MINIO_ENDPOINT", "http://minio:9000"),
            minio_access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
            minio_secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
            manifest_dir=_resolve_path(
                project_root,
                os.getenv("SEED_MANIFEST_PATH", "data/seed_manifests"),
            ),
            ticket_seed_path=_resolve_path(
                project_root,
                os.getenv(
                    "WEEK06_TICKET_SEED_PATH",
                    "data/canonization/tickets/tickets-seed-001.jsonl",
                ),
            ),
            report_dir=_resolve_path(
                project_root,
                os.getenv("WEEK06_REPORT_DIR", "reports/week06"),
            ),
            partition_start_date=os.getenv("WEEK06_PARTITION_START_DATE", "2026-03-01"),
            default_partition=os.getenv("WEEK06_DEFAULT_PARTITION", "2026-04-17"),
            ingest_dry_run=_bool_env("WEEK06_INGEST_DRY_RUN", True),
            ingest_limit=_int_env("WEEK06_INGEST_LIMIT", None),
            data_release_id=os.getenv("WEEK06_DATA_RELEASE_ID", "week06-dev-local"),
            operator=os.getenv("WEEK06_OPERATOR", "student-devbox"),
            week04_report_path=_resolve_path(
                project_root,
                os.getenv("WEEK06_WEEK04_REPORT_PATH", "reports/week04/materialization_report.json"),
            ),
            week05_run_results_path=_resolve_path(
                project_root,
                os.getenv("WEEK06_WEEK05_RUN_RESULTS_PATH", "analytics/target/run_results.json"),
            ),
            metric_registry_path=_resolve_path(
                project_root,
                os.getenv("METRIC_REGISTRY_PATH", "analytics/metric_registry_v1.yml"),
            ),
            git_sha=os.getenv("GIT_SHA", "unknown"),
            trace_id=os.getenv("TRACE_ID", "week06-local"),
        )

    @property
    def backfill_dir(self) -> Path:
        return self.report_dir / "backfill"

    @property
    def checks_dir(self) -> Path:
        return self.report_dir / "checks"

    @property
    def run_evidence_dir(self) -> Path:
        return self.report_dir / "run_evidence"

    def ensure_report_dirs(self) -> None:
        for path in (self.report_dir, self.backfill_dir, self.checks_dir, self.run_evidence_dir):
            path.mkdir(parents=True, exist_ok=True)

    def relative_to_root(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.project_root))
        except ValueError:
            return str(path)
