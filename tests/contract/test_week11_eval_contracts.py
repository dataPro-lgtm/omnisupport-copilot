import json
import sys
from pathlib import Path

import jsonschema

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from evals.week11.dataset import dataset_manifest, load_eval_set
from evals.week11.runner import DEFAULT_DATASET_ID, DEFAULT_DATASET_VERSION


DATASET = PROJECT_ROOT / "evals" / "sets" / "rag_qa_golden_v2_3_0.jsonl"
PREDICTIONS = PROJECT_ROOT / "evals" / "fixtures" / "week11" / "rag_predictions_good.jsonl"
DATASET_SCHEMA = PROJECT_ROOT / "contracts" / "evals" / "eval_dataset.schema.json"
REPORT_SCHEMA = PROJECT_ROOT / "contracts" / "evals" / "eval_report.schema.json"
RELEASE_SCHEMA = PROJECT_ROOT / "contracts" / "release" / "release_manifest_schema.json"
RELEASE_EXAMPLE = PROJECT_ROOT / "contracts" / "release" / "release_manifest_example.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_week11_eval_dataset_samples_match_contract():
    schema = load_json(DATASET_SCHEMA)
    categories = set()
    for line in DATASET.read_text(encoding="utf-8").splitlines():
        sample = json.loads(line)
        jsonschema.validate(sample, schema)
        categories.add(sample["category"])
    assert categories == {"happy", "boundary", "adversarial", "multi_hop"}


def test_week11_dataset_loader_enforces_asset_rules():
    samples = load_eval_set(DATASET)
    assert len(samples) == 8
    assert sum(1 for sample in samples if sample.category == "adversarial") == 2

    manifest = dataset_manifest(
        DATASET,
        dataset_id=DEFAULT_DATASET_ID,
        version=DEFAULT_DATASET_VERSION,
    )
    assert manifest["sample_count"] == 8
    assert manifest["categories"]["multi_hop"] == 2
    assert manifest["digest"].startswith("sha256:")


def test_week11_prediction_fixture_has_matching_case_ids():
    sample_ids = {sample.case_id for sample in load_eval_set(DATASET)}
    prediction_ids = {
        json.loads(line)["case_id"]
        for line in PREDICTIONS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    assert prediction_ids == sample_ids


def test_week11_release_manifest_binds_eval_and_business_slo():
    jsonschema.validate(load_json(RELEASE_EXAMPLE), load_json(RELEASE_SCHEMA))
    example = load_json(RELEASE_EXAMPLE)
    assert example["eval_dataset"]["id"] == DEFAULT_DATASET_ID
    assert example["eval_dataset"]["version"] == DEFAULT_DATASET_VERSION
    assert example["judge_calibration"]["trust_level"] == "high"
    assert example["business_slo"]["metrics"]["pii_leak_rate"]["status"] == "pass"
