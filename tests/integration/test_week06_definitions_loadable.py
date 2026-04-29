from pipelines.definitions import defs


def test_week06_definitions_are_loadable():
    asset_keys = {"/".join(asset_key.path) for asset_key in defs.resolve_all_asset_keys()}

    assert "week06/source/seed_manifests" in asset_keys
    assert "week06/factory/manifest_gate" in asset_keys
    assert "week06/ingestion/raw_ticket_events_partitioned" in asset_keys
    assert "week06/silver/ticket_fact_partitioned" in asset_keys
    assert "week06/ops/run_evidence_report" in asset_keys
    assert defs.resolve_job_def("week06_data_factory").name == "week06_data_factory"


def test_week06_resources_are_registered():
    resource_defs = defs.get_repository_def().get_top_level_resources()

    assert "week06_postgres" in resource_defs
    assert "week06_minio" in resource_defs
    assert "week06_reports" in resource_defs
