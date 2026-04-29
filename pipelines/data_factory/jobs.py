"""Week06 Dagster jobs."""

from dagster import AssetSelection, define_asset_job

from pipelines.data_factory.asset_keys import WEEK06_ASSET_KEYS

week06_data_factory_job = define_asset_job(
    name="week06_data_factory",
    selection=AssetSelection.assets(*WEEK06_ASSET_KEYS),
    description="Week06 data factory asset graph with daily partitions and evidence output.",
)
