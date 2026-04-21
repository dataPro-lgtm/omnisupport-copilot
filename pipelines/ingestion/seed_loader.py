"""Seed Loader — 从 seed manifest 驱动数据采集

Week01-02: 提供完整的 manifest 驱动采集框架。
Week03: 接入真实 MinIO 上传 + PostgreSQL 写入。

使用方式:
    python -m pipelines.ingestion.seed_loader --manifest-dir data/seed_manifests
    python -m pipelines.ingestion.seed_loader \
        --manifest-path data/seed_manifests/manifest_tickets_synthetic_v1.json
"""

import argparse
import hashlib
import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import jsonschema

logger = logging.getLogger(__name__)


# ── Schema 路径 ───────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent.parent
MANIFEST_SCHEMA_PATH = PROJECT_ROOT / "data" / "seed_manifests" / "source_manifest_schema.json"

CONTRACT_REGISTRY = {
    "omni://contracts/data/doc_asset/v1": {
        "modalities": {"document"},
        "source_types": {"help_center", "faq", "release_notes", "api_doc", "pdf_manual", "community", "other"},
        "asset_types": {"pdf", "html", "faq", "release_notes", "api_doc", "community_post", "other"},
    },
    "omni://contracts/data/ticket/v1": {
        "modalities": {"structured"},
        "source_types": {"ticket_export"},
        "asset_types": {"json", "jsonl", "csv", "parquet"},
    },
    "omni://contracts/data/audio_asset/v1": {
        "modalities": {"audio"},
        "source_types": {"call_recording", "tts_synthetic", "other"},
        "asset_types": {"wav", "mp3", "m4a", "flac", "jsonl", "other"},
    },
    "omni://contracts/data/video_asset/v1": {
        "modalities": {"video"},
        "source_types": {"tutorial_video", "screencast", "other"},
        "asset_types": {"mp4", "mov", "mkv", "jsonl", "other"},
    },
}

DEFAULT_GATE_POLICY = {
    "on_missing_checksum": "warn",
    "on_partial_metadata": "warn",
    "on_missing_metadata": "quarantine",
    "on_pii_gap": "quarantine",
    "on_contract_mismatch": "reject",
    "on_unknown_license": "reject",
}

JUDGMENT_ORDER = {
    "accept": 0,
    "warn": 1,
    "quarantine": 2,
    "reject": 3,
}


# ── 数据类 ────────────────────────────────────────────────────────────────────

@dataclass
class AssetJudgment:
    source_id: str
    contract_ref: str
    gate_judgment: str
    reasons: list[str] = field(default_factory=list)


@dataclass
class IngestResult:
    manifest_id: str
    modality: str
    total_assets: int
    success_count: int = 0
    skip_count: int = 0
    fail_count: int = 0
    warn_count: int = 0
    quarantine_count: int = 0
    errors: list[str] = field(default_factory=list)
    run_evidence: list[AssetJudgment] = field(default_factory=list)
    run_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def success_rate(self) -> float:
        if self.total_assets == 0:
            return 0.0
        return self.success_count / self.total_assets

    @property
    def accepted_count(self) -> int:
        return self.success_count - self.warn_count

    def to_report_dict(self) -> dict[str, Any]:
        return {
            "manifest_id": self.manifest_id,
            "modality": self.modality,
            "total_assets": self.total_assets,
            "accepted_count": self.accepted_count,
            "warn_count": self.warn_count,
            "quarantine_count": self.quarantine_count,
            "reject_count": self.fail_count,
            "run_at": self.run_at,
            "errors": self.errors,
            "run_evidence": [asdict(judgment) for judgment in self.run_evidence],
        }


# ── Manifest Validator ────────────────────────────────────────────────────────

class ManifestValidator:
    """
    校验 seed manifest 的 schema 合法性。

    设计选择：分两级校验
    1. 结构校验：使用 jsonschema 校验 source_manifest_schema.json
    2. 业务校验：检查 license_tag、pii_level 等关键业务字段
    """

    def __init__(self, schema_path: Path = MANIFEST_SCHEMA_PATH):
        if schema_path.exists():
            self._schema = json.loads(schema_path.read_text())
        else:
            logger.warning(f"Manifest schema not found at {schema_path}, skipping strict validation")
            self._schema = None

    def validate(self, manifest: dict) -> list[str]:
        """
        校验 manifest，返回错误列表。空列表表示通过。
        """
        errors: list[str] = []

        # 1. JSON Schema 结构校验
        if self._schema:
            try:
                jsonschema.validate(manifest, self._schema)
            except jsonschema.ValidationError as e:
                errors.append(f"Schema violation: {e.message}")
                return errors  # 结构错误，无需继续校验

        # 2. 业务规则校验
        errors.extend(self._validate_business_rules(manifest))
        return errors

    def _validate_business_rules(self, manifest: dict) -> list[str]:
        errors = []

        # license_tag 不允许 unknown 进入 canonized 状态
        if (manifest.get("license_tag") == "unknown"
                and manifest.get("canonization_status") == "canonized"):
            errors.append("Cannot canonize assets with unknown license_tag")

        # assets 列表不允许有重复 source_id
        assets = manifest.get("assets", [])
        source_ids = [a.get("source_id") for a in assets]
        if len(source_ids) != len(set(source_ids)):
            errors.append("Duplicate source_id found in assets list")

        # modality 与 source_type 一致性检查
        modality = manifest.get("modality")
        source_type = manifest.get("source_type")
        invalid_combos = {
            ("document", "call_recording"),
            ("audio", "pdf_manual"),
            ("audio", "help_center"),
            ("video", "ticket_export"),
        }
        if (modality, source_type) in invalid_combos:
            errors.append(f"Inconsistent modality '{modality}' with source_type '{source_type}'")

        # contract_ref 必须已知，且与 manifest 的 modality/source_type 对齐
        contract_ref = manifest.get("contract_ref")
        registry_entry = CONTRACT_REGISTRY.get(contract_ref)
        if contract_ref and not registry_entry:
            errors.append(f"Unknown contract_ref: {contract_ref}")
        elif registry_entry:
            if modality != "multimodal" and modality not in registry_entry["modalities"]:
                errors.append(
                    f"contract_ref '{contract_ref}' is incompatible with modality '{modality}'"
                )
            if source_type not in registry_entry["source_types"]:
                errors.append(
                    f"contract_ref '{contract_ref}' is incompatible with source_type '{source_type}'"
                )

        # load_mode 对 selection_window 的要求
        load_mode = manifest.get("load_mode")
        selection_window = manifest.get("selection_window", {})
        if load_mode == "incremental_cursor":
            required_window_fields = ["cursor_field", "cursor_start"]
            for field_name in required_window_fields:
                if not selection_window.get(field_name):
                    errors.append(
                        f"load_mode '{load_mode}' requires selection_window.{field_name}"
                    )
        elif load_mode == "cdc":
            if not selection_window.get("cursor_field") and not selection_window.get("watermark_field"):
                errors.append(
                    "load_mode 'cdc' requires selection_window.cursor_field or selection_window.watermark_field"
                )
        elif load_mode == "replay":
            if not selection_window.get("replay_from_batch"):
                errors.append("load_mode 'replay' requires selection_window.replay_from_batch")
        elif load_mode == "backfill":
            if not selection_window.get("start_at") or not selection_window.get("end_at"):
                errors.append("load_mode 'backfill' requires selection_window.start_at and selection_window.end_at")

        # gate_policy 仅允许声明已知动作
        gate_policy = manifest.get("gate_policy", {})
        unknown_policy_keys = set(gate_policy) - set(DEFAULT_GATE_POLICY)
        if unknown_policy_keys:
            errors.append(
                f"Unknown gate_policy keys: {', '.join(sorted(unknown_policy_keys))}"
            )
        for key, action in gate_policy.items():
            if action not in JUDGMENT_ORDER:
                errors.append(f"Invalid gate_policy action '{action}' for {key}")

        # asset 级别 contract_ref 仅允许在 multimodal manifest 中覆盖
        for asset in assets:
            asset_contract_ref = asset.get("contract_ref")
            resolved_contract_ref = asset_contract_ref or contract_ref
            if asset_contract_ref and modality != "multimodal" and asset_contract_ref != contract_ref:
                errors.append(
                    "Asset-level contract_ref override is only allowed for modality='multimodal'"
                )

            registry_entry = CONTRACT_REGISTRY.get(resolved_contract_ref)
            if resolved_contract_ref and not registry_entry:
                errors.append(
                    f"Unknown asset-level contract_ref '{resolved_contract_ref}' for source_id '{asset.get('source_id')}'"
                )
                continue

            asset_type = asset.get("asset_type")
            if registry_entry and asset_type not in registry_entry["asset_types"]:
                errors.append(
                    f"asset_type '{asset_type}' is incompatible with contract_ref '{resolved_contract_ref}'"
                )

        return errors


# ── Asset Iterator ────────────────────────────────────────────────────────────

class SeedLoader:
    """
    从 manifest 目录加载、校验、迭代所有资产。

    Week03: 接入真实 MinIO upload 和 PostgreSQL metadata 写入。
    """

    def __init__(
        self,
        manifest_dir: Path,
        manifest_paths: list[Path] | None = None,
        batch_id: str | None = None,
        dry_run: bool = True,
        report_path: Path | None = None,
    ):
        self.manifest_dir = manifest_dir
        self.manifest_paths = manifest_paths or []
        self.batch_id = batch_id or f"batch-{datetime.now(timezone.utc).strftime('%Y%m%d')}-auto"
        self.dry_run = dry_run
        self.report_path = report_path
        self.validator = ManifestValidator()
        self.rejected_manifests: list[dict[str, Any]] = []

    def _iter_manifest_paths(self) -> list[Path]:
        if self.manifest_paths:
            paths: list[Path] = []
            seen: set[Path] = set()
            for path in self.manifest_paths:
                if path.name.startswith("source_manifest"):
                    raise ValueError(f"Schema file is not a runnable manifest: {path}")
                if not path.exists():
                    raise FileNotFoundError(f"Manifest file not found: {path}")
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                paths.append(path)
            return paths

        return sorted(
            path
            for path in self.manifest_dir.glob("*.json")
            if not path.name.startswith("source_manifest")
        )

    def load_manifests(self) -> list[dict]:
        """加载 manifest 文件（显式路径优先，其次扫描目录）"""
        manifests = []
        for path in self._iter_manifest_paths():
            try:
                data = json.loads(path.read_text())
                manifests.append(data)
                logger.info(f"Loaded: {path.name}")
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in {path.name}: {e}")
        return manifests

    def validate_all(self, manifests: list[dict]) -> tuple[list[dict], list[dict]]:
        """返回 (valid_manifests, rejected_manifests)"""
        valid, rejected = [], []
        for m in manifests:
            errors = self.validator.validate(m)
            if errors:
                logger.warning(f"Manifest {m.get('manifest_id')} rejected: {errors}")
                rejected.append({**m, "_validation_errors": errors})
            else:
                valid.append(m)
        return valid, rejected

    def iter_assets(self, manifest: dict) -> Iterator[dict]:
        """迭代 manifest 中的所有资产，注入采集元数据"""
        for asset_item in manifest.get("assets", []):
            yield {
                **asset_item,
                "_manifest_id": manifest["manifest_id"],
                "_batch_id": self.batch_id,
                "_modality": manifest["modality"],
                "_license_tag": manifest["license_tag"],
                "_product_line": manifest.get("product_line"),
                "_ingest_config": manifest.get("ingest_config", {}),
            }

    def compute_fingerprint(self, content: bytes) -> str:
        """计算 SHA-256 source_fingerprint"""
        return hashlib.sha256(content).hexdigest()

    def run(self) -> list[IngestResult]:
        """
        执行完整的 seed loading 流程。

        Week01-02: dry_run=True，仅输出日志不实际写入。
        Week03: dry_run=False，接入 MinIO + PostgreSQL。
        """
        manifests = self.load_manifests()
        valid, rejected = self.validate_all(manifests)
        self.rejected_manifests = rejected

        results = []
        for manifest in valid:
            result = self._process_manifest(manifest)
            results.append(result)

        # 输出汇总报告
        self._print_report(results, rejected)
        if self.report_path:
            self._write_report_json(results, rejected)
        return results

    def _process_manifest(self, manifest: dict) -> IngestResult:
        result = IngestResult(
            manifest_id=manifest["manifest_id"],
            modality=manifest["modality"],
            total_assets=len(manifest.get("assets", [])),
        )

        for asset in self.iter_assets(manifest):
            try:
                gate_judgment, reasons = self._evaluate_asset_gate(manifest, asset)
                result.run_evidence.append(
                    AssetJudgment(
                        source_id=asset["source_id"],
                        contract_ref=self._resolve_contract_ref(manifest, asset),
                        gate_judgment=gate_judgment,
                        reasons=reasons,
                    )
                )

                if gate_judgment == "reject":
                    logger.error(
                        "[dry-run][reject] %s (%s): %s",
                        asset["source_id"],
                        asset["_modality"],
                        "; ".join(reasons) or "rejected by gate policy",
                    )
                    result.fail_count += 1
                    result.errors.extend(reasons)
                    continue

                if gate_judgment == "quarantine":
                    logger.warning(
                        "[dry-run][quarantine] Hold %s (%s): %s",
                        asset["source_id"],
                        asset["_modality"],
                        "; ".join(reasons) or "quarantined by gate policy",
                    )
                    result.skip_count += 1
                    result.quarantine_count += 1
                    continue

                if gate_judgment == "warn":
                    logger.warning(
                        "[dry-run][warn] Would ingest %s (%s): %s",
                        asset["source_id"],
                        asset["_modality"],
                        "; ".join(reasons) or "warning only",
                    )
                    result.success_count += 1
                    result.warn_count += 1
                    continue

                if self.dry_run:
                    logger.info(
                        "[dry-run][accept] Would ingest: %s (%s) from %s",
                        asset["source_id"],
                        asset["_modality"],
                        asset["source_url_or_path"],
                    )
                    result.success_count += 1
                else:
                    # TODO(Week03): 真实采集逻辑
                    # 1. 下载/读取原始文件
                    # 2. 计算 source_fingerprint
                    # 3. 上传到 MinIO raw zone
                    # 4. 写入 PostgreSQL source_manifest + raw_*_asset 元数据
                    raise NotImplementedError("Real ingest not implemented until Week03")

            except Exception as e:
                logger.error(f"Failed to ingest {asset.get('source_id')}: {e}")
                result.fail_count += 1
                result.errors.append(str(e))

        return result

    def _resolve_contract_ref(self, manifest: dict, asset: dict) -> str:
        return asset.get("contract_ref") or manifest["contract_ref"]

    def _combine_judgments(self, current: str, candidate: str) -> str:
        if JUDGMENT_ORDER[candidate] > JUDGMENT_ORDER[current]:
            return candidate
        return current

    def _evaluate_asset_gate(self, manifest: dict, asset: dict) -> tuple[str, list[str]]:
        policy = {**DEFAULT_GATE_POLICY, **manifest.get("gate_policy", {})}
        judgment = "accept"
        reasons: list[str] = []

        contract_ref = self._resolve_contract_ref(manifest, asset)
        registry_entry = CONTRACT_REGISTRY.get(contract_ref)
        asset_type = asset.get("asset_type")

        if not registry_entry:
            return "reject", [f"Unknown contract_ref '{contract_ref}'"]

        if asset_type not in registry_entry["asset_types"]:
            reasons.append(
                f"asset_type '{asset_type}' does not match contract_ref '{contract_ref}'"
            )
            judgment = self._combine_judgments(judgment, policy["on_contract_mismatch"])

        metadata_status = asset.get("metadata_status") or "unknown"
        if metadata_status == "missing":
            reasons.append("metadata_status=missing")
            judgment = self._combine_judgments(judgment, policy["on_missing_metadata"])
        elif metadata_status == "partial":
            reasons.append("metadata_status=partial")
            judgment = self._combine_judgments(judgment, policy["on_partial_metadata"])

        if not asset.get("checksum_sha256"):
            reasons.append("checksum_sha256 missing")
            judgment = self._combine_judgments(judgment, policy["on_missing_checksum"])

        if manifest.get("license_tag") == "unknown":
            reasons.append("license_tag=unknown")
            judgment = self._combine_judgments(judgment, policy["on_unknown_license"])

        pii_scan_required = manifest.get("ingest_config", {}).get("pii_scan", False)
        pii_scan_status = asset.get("pii_scan_status") or "unknown"
        if pii_scan_required and pii_scan_status in {"not_run", "unknown"}:
            reasons.append(f"pii_scan_status={pii_scan_status}")
            judgment = self._combine_judgments(judgment, policy["on_pii_gap"])
        elif pii_scan_status == "suspected":
            reasons.append("pii_scan_status=suspected")
            judgment = self._combine_judgments(judgment, "quarantine")

        return judgment, reasons

    def _print_report(self, results: list[IngestResult], rejected: list[dict]):
        print("\n" + "=" * 60)
        print("  SEED LOADER RUN REPORT")
        print("=" * 60)
        print(f"  Batch ID    : {self.batch_id}")
        print(f"  Dry Run     : {self.dry_run}")
        print(f"  Manifests   : {len(results)} valid, {len(rejected)} rejected")

        total_assets = sum(r.total_assets for r in results)
        total_accept = sum(r.accepted_count for r in results)
        total_warn = sum(r.warn_count for r in results)
        total_quarantine = sum(r.quarantine_count for r in results)
        total_reject = sum(r.fail_count for r in results)

        print(
            "  Assets      : "
            f"{total_assets} total, "
            f"{total_accept} accept, {total_warn} warn, "
            f"{total_quarantine} quarantine, {total_reject} reject"
        )

        for result in results:
            status = "✓" if result.fail_count == 0 else "✗"
            print(
                f"  {status} {result.manifest_id} [{result.modality}] "
                f"(accept={result.accepted_count}, warn={result.warn_count}, "
                f"quarantine={result.quarantine_count}, reject={result.fail_count})"
            )
            for err in result.errors:
                print(f"      ERROR: {err}")
            for evidence in result.run_evidence:
                print(
                    f"      {evidence.gate_judgment.upper():<10} "
                    f"{evidence.source_id} -> {evidence.contract_ref}"
                )

        if rejected:
            print(f"\n  REJECTED ({len(rejected)} manifests):")
            for m in rejected:
                print(f"  - {m.get('manifest_id')}: {m.get('_validation_errors')}")

        print("=" * 60 + "\n")

    def _write_report_json(self, results: list[IngestResult], rejected: list[dict]):
        report_payload = {
            "batch_id": self.batch_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "dry_run": self.dry_run,
            "manifest_dir": str(self.manifest_dir),
            "manifest_paths": [str(path) for path in self.manifest_paths],
            "summary": {
                "accepted_count": sum(result.accepted_count for result in results),
                "warn_count": sum(result.warn_count for result in results),
                "quarantine_count": sum(result.quarantine_count for result in results),
                "reject_count": sum(result.fail_count for result in results),
                "rejected_manifests": len(rejected),
            },
            "results": [result.to_report_dict() for result in results],
            "rejected_manifests": [
                {
                    "manifest_id": manifest.get("manifest_id"),
                    "validation_errors": manifest.get("_validation_errors", []),
                }
                for manifest in rejected
            ],
        }

        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text(
            json.dumps(report_payload, ensure_ascii=False, indent=2) + "\n"
        )
        logger.info("Wrote run evidence report to %s", self.report_path)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="OmniSupport Seed Loader")
    parser.add_argument(
        "--manifest-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "seed_manifests",
    )
    parser.add_argument(
        "--manifest-path",
        dest="manifest_paths",
        action="append",
        type=Path,
        default=None,
        help="可重复传入：只运行指定 manifest 文件，适合课程按周锁定基线范围",
    )
    parser.add_argument(
        "--batch-id",
        type=str,
        default=None,
        help="采集批次 ID，默认自动生成",
    )
    parser.add_argument(
        "--no-dry-run",
        action="store_true",
        help="真实执行（Week03 前不要开启）",
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        default=None,
        help="可选：把本次 gate judgment / run evidence 写成 JSON 报告",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    loader = SeedLoader(
        manifest_dir=args.manifest_dir,
        manifest_paths=args.manifest_paths,
        batch_id=args.batch_id,
        dry_run=not args.no_dry_run,
        report_path=args.report_json,
    )
    results = loader.run()

    failed = [r for r in results if r.fail_count > 0]
    sys.exit(1 if failed or loader.rejected_manifests else 0)


if __name__ == "__main__":
    main()
