"""Dagster Definitions — 项目入口

所有资产、作业、传感器、调度统一在此注册。
Dagster dev 命令会自动发现此文件。
"""

from dagster import Definitions, load_asset_checks_from_modules, load_assets_from_modules

from pipelines.data_factory import assets as data_factory_assets
from pipelines.data_factory import checks as data_factory_checks
from pipelines.data_factory.jobs import week06_data_factory_job
from pipelines.data_factory.resources import build_week06_resources
from pipelines.ingestion import assets as ingestion_assets
from pipelines.parse_normalize import assets as parse_assets
from pipelines.lakehouse import assets as lakehouse_assets
from pipelines.ingestion.assets import ingest_all_job


all_assets = load_assets_from_modules(
    [
        ingestion_assets,
        parse_assets,
        lakehouse_assets,
        data_factory_assets,
    ]
)

all_asset_checks = load_asset_checks_from_modules([data_factory_checks])

defs = Definitions(
    assets=all_assets,
    asset_checks=all_asset_checks,
    jobs=[ingest_all_job, week06_data_factory_job],
    resources=build_week06_resources(),
)
