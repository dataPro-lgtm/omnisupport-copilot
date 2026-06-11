from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

pytest.importorskip("dagster")

from pipelines.definitions import defs


def test_week07_parse_assets_are_registered_without_breaking_existing_defs():
    asset_keys = {"/".join(asset_key.path) for asset_key in defs.resolve_all_asset_keys()}

    assert "parsed_doc_sections" in asset_keys
    assert "knowledge_chunks" in asset_keys
    assert "week06/source/seed_manifests" in asset_keys
    assert "build_knowledge_index" in asset_keys
