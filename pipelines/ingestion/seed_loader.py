"""Seed Loader — 从 seed manifest 驱动数据采集

Week01-02: 提供完整的 manifest 驱动采集框架。
Week03: 接入真实 MinIO 上传 + PostgreSQL 写入。

使用方式:
    python -m pipelines.ingestion.seed_loader --manifest-dir data/seed_manifests
"""

import argparse
import hashlib
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import jsonschema

logger = logging.getLogger(__name__)


# ── Schema 路径 ───────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent.parent
MANIFEST_SCHEMA_PATH = PROJECT_ROOT / "data" / "seed_manifests" / "source_manifest_schema.json"
DOC_CONTRACT_PATH = PROJECT_ROOT / "contracts" / "data" / "doc_asset_contract.json"
TICKET_CONTRACT_PATH = PROJECT_ROOT / "contracts" / "data" / "ticket_contract.json"


# ── 数据类 ────────────────────────────────────────────────────────────────────

@dataclass
class IngestResult:
    manifest_id: str
    modality: str
    total_assets: int
    success_count: int = 0
    skip_count: int = 0
    fail_count: int = 0
    errors: list[str] = field(default_factory=list)
    run_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def success_rate(self) -> float:
        if self.total_assets == 0:
            return 0.0
        return self.success_count / self.total_assets


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
        batch_id: str | None = None,
        dry_run: bool = True,
    ):
        self.manifest_dir = manifest_dir
        self.batch_id = batch_id or f"batch-{datetime.now(timezone.utc).strftime('%Y%m%d')}-auto"
        self.dry_run = dry_run
        self.validator = ManifestValidator()

    def load_manifests(self) -> list[dict]:
        """加载目录下所有 manifest 文件（跳过 schema 文件）"""
        manifests = []
        for path in sorted(self.manifest_dir.glob("*.json")):
            if path.name.startswith("source_manifest"):
                continue
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

        results = []
        for manifest in valid:
            result = self._process_manifest(manifest)
            results.append(result)

        # 输出汇总报告
        self._print_report(results, rejected)
        return results

    def _process_manifest(self, manifest: dict) -> IngestResult:
        result = IngestResult(
            manifest_id=manifest["manifest_id"],
            modality=manifest["modality"],
            total_assets=len(manifest.get("assets", [])),
        )

        for asset in self.iter_assets(manifest):
            try:
                if self.dry_run:
                    logger.info(
                        f"[dry-run] Would ingest: {asset['source_id']} "
                        f"({asset['_modality']}) from {asset['source_url_or_path']}"
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

    def _print_report(self, results: list[IngestResult], rejected: list[dict]):
        print("\n" + "=" * 60)
        print("  SEED LOADER RUN REPORT")
        print("=" * 60)
        print(f"  Batch ID    : {self.batch_id}")
        print(f"  Dry Run     : {self.dry_run}")
        print(f"  Manifests   : {len(results)} valid, {len(rejected)} rejected")

        total_assets = sum(r.total_assets for r in results)
        total_success = sum(r.success_count for r in results)
        total_fail = sum(r.fail_count for r in results)

        print(f"  Assets      : {total_assets} total, {total_success} ok, {total_fail} failed")

        for result in results:
            status = "✓" if result.fail_count == 0 else "✗"
            print(f"  {status} {result.manifest_id} [{result.modality}] "
                  f"({result.success_count}/{result.total_assets})")
            for err in result.errors:
                print(f"      ERROR: {err}")

        if rejected:
            print(f"\n  REJECTED ({len(rejected)} manifests):")
            for m in rejected:
                print(f"  - {m.get('manifest_id')}: {m.get('_validation_errors')}")

        print("=" * 60 + "\n")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="OmniSupport Seed Loader")
    parser.add_argument(
        "--manifest-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "seed_manifests",
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
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    loader = SeedLoader(
        manifest_dir=args.manifest_dir,
        batch_id=args.batch_id,
        dry_run=not args.no_dry_run,
    )
    results = loader.run()

    failed = [r for r in results if r.fail_count > 0]
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
