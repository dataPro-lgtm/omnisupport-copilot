"""Week06 daily partition definition."""

from __future__ import annotations

from dagster import DailyPartitionsDefinition

from pipelines.resources.config import DataFactorySettings


def get_week06_partitions_def(settings: DataFactorySettings | None = None) -> DailyPartitionsDefinition:
    resolved = settings or DataFactorySettings.from_env()
    return DailyPartitionsDefinition(start_date=resolved.partition_start_date)


def default_partition_key(settings: DataFactorySettings | None = None) -> str:
    resolved = settings or DataFactorySettings.from_env()
    return resolved.default_partition
