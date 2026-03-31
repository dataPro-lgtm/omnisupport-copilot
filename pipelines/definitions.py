"""Dagster Definitions — 项目入口

所有资产、作业、传感器、调度统一在此注册。
Dagster dev 命令会自动发现此文件。
"""

from dagster import Definitions, load_assets_from_modules

from pipelines.ingestion import assets as ingestion_assets
from pipelines.parse_normalize import assets as parse_assets
from pipelines.lakehouse import assets as lakehouse_assets
from pipelines.ingestion.assets import ingest_all_job


all_assets = load_assets_from_modules([
    ingestion_assets,
    parse_assets,
    lakehouse_assets,
])

defs = Definitions(
    assets=all_assets,
    jobs=[ingest_all_job],
)
