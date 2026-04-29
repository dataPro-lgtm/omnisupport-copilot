"""Report path resource for Week06 run evidence."""

from dagster import ConfigurableResource


class ReportPathResource(ConfigurableResource):
    report_dir: str
    backfill_dir: str
    checks_dir: str
    run_evidence_dir: str
