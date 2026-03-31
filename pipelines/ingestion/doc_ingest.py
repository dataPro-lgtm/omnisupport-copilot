"""Document Ingest Pipeline — 文档批量采集

从本地文件系统或 HTTP URL 读取文档，上传到 MinIO raw zone，
写入 PostgreSQL raw_doc_asset + knowledge_doc 元数据。

执行方式:
    python -m pipelines.ingestion.doc_ingest \
        --manifest data/seed_manifests/manifest_workspace_helpcenter_v1.json \
        --source-dir /path/to/local/docs
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import mimetypes
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent


# ── MinIO 客户端封装 ──────────────────────────────────────────────────────────

class MinIOClient:
    """S3 兼容对象存储客户端"""

    def __init__(self):
        import boto3
        import os
        self._s3 = boto3.client(
            "s3",
            endpoint_url=os.environ.get("MINIO_ENDPOINT", "http://localhost:9000"),
            aws_access_key_id=os.environ.get("MINIO_ACCESS_KEY", "minioadmin"),
            aws_secret_access_key=os.environ.get("MINIO_SECRET_KEY", "minioadmin"),
        )

    def upload_bytes(self, bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        import io
        self._s3.upload_fileobj(
            io.BytesIO(data),
            bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )
        return f"s3://{bucket}/{key}"

    def upload_file(self, bucket: str, key: str, local_path: Path) -> str:
        content_type, _ = mimetypes.guess_type(str(local_path))
        self._s3.upload_file(
            str(local_path),
            bucket,
            key,
            ExtraArgs={"ContentType": content_type or "application/octet-stream"},
        )
        return f"s3://{bucket}/{key}"

    def object_exists(self, bucket: str, key: str) -> bool:
        try:
            self._s3.head_object(Bucket=bucket, Key=key)
            return True
        except Exception:
            return False


# ── 文档读取器 ────────────────────────────────────────────────────────────────

async def read_asset_bytes(source_url_or_path: str, source_dir: Path | None) -> bytes | None:
    """
    从本地路径或 s3:// 路径读取文档字节。
    HTTP URL 暂不自动抓取（Week03 课程内按 manifest 预先下载）。
    """
    if source_url_or_path.startswith("s3://"):
        # 本地开发阶段：从 source_dir 映射文件名读取
        filename = Path(urlparse(source_url_or_path).path).name
        if source_dir:
            local = source_dir / filename
            if local.exists():
                return local.read_bytes()
        logger.warning(f"Cannot read s3 asset locally: {source_url_or_path}")
        return None

    local = Path(source_url_or_path)
    if local.exists():
        return local.read_bytes()

    if source_dir:
        alt = source_dir / local.name
        if alt.exists():
            return alt.read_bytes()

    return None


# ── DB 写入 ───────────────────────────────────────────────────────────────────

async def upsert_raw_doc_asset(conn, asset: dict, batch_id: str, raw_object_path: str, fingerprint: str):
    """写入 raw_doc_asset Bronze 层"""
    await conn.execute(
        """
        INSERT INTO raw_doc_asset (
            source_id, asset_type, raw_object_path, manifest_id,
            ingest_batch_id, license_tag, product_line, source_fingerprint,
            source_url, pii_level, quality_gate, schema_version, ingest_ts
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
        ON CONFLICT (source_id) DO UPDATE SET
            raw_object_path = EXCLUDED.raw_object_path,
            source_fingerprint = EXCLUDED.source_fingerprint,
            ingest_batch_id = EXCLUDED.ingest_batch_id,
            quality_gate = 'pending'
        """,
        asset["source_id"],
        asset.get("asset_type", "unknown"),
        raw_object_path,
        asset.get("_manifest_id", ""),
        batch_id,
        asset.get("_license_tag", "unknown"),
        asset.get("_product_line"),
        fingerprint,
        asset.get("source_url_or_path"),
        "none",       # doc 资产默认 pii_level=none，parse 阶段再扫描
        "pending",
        "raw_doc_asset_v1",
        datetime.now(timezone.utc),
    )


async def upsert_knowledge_doc(conn, asset: dict, source_id: str, batch_id: str):
    """写入 knowledge_doc Silver 层（元数据，content 在 parse 阶段填充）"""
    import uuid as _uuid
    doc_id = str(_uuid.uuid5(_uuid.NAMESPACE_URL, source_id))

    await conn.execute(
        """
        INSERT INTO knowledge_doc (
            doc_id, source_id, asset_type, product_line,
            language, source_url, license_tag, quality_gate,
            data_release_id, created_at
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
        ON CONFLICT (doc_id) DO NOTHING
        """,
        doc_id,
        source_id,
        asset.get("asset_type", "unknown"),
        asset.get("_product_line"),
        "en",
        asset.get("source_url_or_path"),
        asset.get("_license_tag", "unknown"),
        "pending",
        "data-v0.1.0",
        datetime.now(timezone.utc),
    )
    return doc_id


# ── 主流程 ────────────────────────────────────────────────────────────────────

async def run_doc_ingest(
    manifest_path: Path,
    source_dir: Path | None,
    batch_id: str,
    dry_run: bool = False,
) -> dict:
    from pipelines.ingestion.db import acquire
    from pipelines.ingestion.seed_loader import SeedLoader, ManifestValidator

    manifest = json.loads(manifest_path.read_text())
    errs = ManifestValidator().validate(manifest)
    if errs:
        logger.error(f"Manifest invalid: {errs}")
        return {"errors": errs}

    stats = {
        "total": 0, "uploaded": 0, "skipped": 0,
        "db_inserted": 0, "errors": 0,
        "batch_id": batch_id,
    }

    minio: MinIOClient | None = None
    if not dry_run:
        try:
            minio = MinIOClient()
        except Exception as e:
            logger.warning(f"MinIO unavailable ({e}), will skip upload")

    loader = SeedLoader(manifest_path.parent, batch_id=batch_id, dry_run=dry_run)

    async with acquire() as conn:
        for asset in loader.iter_assets(manifest):
            stats["total"] += 1
            source_id = asset["source_id"]
            source_path = asset["source_url_or_path"]

            if dry_run:
                logger.info(f"[dry-run] Would ingest doc: {source_id}")
                stats["skipped"] += 1
                continue

            # ── 读取文件字节 ─────────────────────────────────────────────────
            raw_bytes = await read_asset_bytes(source_path, source_dir)
            if raw_bytes is None:
                logger.warning(f"File not found, skipping: {source_path}")
                stats["skipped"] += 1
                continue

            fingerprint = hashlib.sha256(raw_bytes).hexdigest()

            # ── MinIO 上传 ────────────────────────────────────────────────────
            raw_object_path = source_path   # 默认保持原路径
            if minio:
                bucket = "omni-raw-documents"
                modality = asset.get("_modality", "document")
                product = asset.get("_product_line", "unknown")
                key = f"{product}/{asset.get('asset_type', 'misc')}/{Path(source_path).name}"

                if not minio.object_exists(bucket, key):
                    try:
                        ext = Path(source_path).suffix.lower()
                        content_type = {
                            ".pdf": "application/pdf",
                            ".html": "text/html",
                            ".json": "application/json",
                        }.get(ext, "application/octet-stream")
                        raw_object_path = minio.upload_bytes(bucket, key, raw_bytes, content_type)
                        stats["uploaded"] += 1
                    except Exception as e:
                        logger.error(f"MinIO upload failed for {source_id}: {e}")
                        stats["errors"] += 1
                        continue
                else:
                    raw_object_path = f"s3://{bucket}/{key}"
                    logger.debug(f"Already in MinIO, skipping upload: {key}")

            # ── DB 写入 ───────────────────────────────────────────────────────
            try:
                async with conn.transaction():
                    await upsert_raw_doc_asset(conn, asset, batch_id, raw_object_path, fingerprint)
                    await upsert_knowledge_doc(conn, asset, source_id, batch_id)
                stats["db_inserted"] += 1
            except Exception as e:
                logger.error(f"DB write failed for {source_id}: {e}")
                stats["errors"] += 1

    _log_doc_summary(stats)
    return stats


def _log_doc_summary(stats: dict):
    logger.info(
        f"\n{'='*50}\n"
        f"  DOC INGEST SUMMARY\n"
        f"  Batch    : {stats['batch_id']}\n"
        f"  Total    : {stats['total']}\n"
        f"  Uploaded : {stats['uploaded']}\n"
        f"  Skipped  : {stats['skipped']}\n"
        f"  DB insert: {stats['db_inserted']}\n"
        f"  Errors   : {stats['errors']}\n"
        f"{'='*50}"
    )


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Document Ingest Pipeline")
    parser.add_argument("--manifest", type=Path, required=True, help="seed manifest JSON 文件")
    parser.add_argument("--source-dir", type=Path, default=None, help="本地文档目录（可选）")
    parser.add_argument("--batch-id", default=f"batch-{datetime.now(timezone.utc).strftime('%Y%m%d')}-001")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    stats = asyncio.run(
        run_doc_ingest(args.manifest, args.source_dir, args.batch_id, args.dry_run)
    )
    sys.exit(1 if stats.get("errors", 0) > 0 else 0)


if __name__ == "__main__":
    main()
