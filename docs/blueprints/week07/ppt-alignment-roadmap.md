# Week07 PPT Alignment Roadmap

This note maps the Week07 lesson deck to code paths in the repository. It separates the classroom-safe implementation from optional production adapters.

## L01 Parse: IDP Replaces Raw Text Extraction

| Lesson concept | Repository path | Runtime status |
|---|---|---|
| PDF type detection | `pipelines/parse/pdf_typer.py` | Implemented as deterministic helper with PyMuPDF/pypdf fallback |
| Marker / Docling IDP route | `pipelines/parse/marker_pipeline.py` | Optional adapter, used by `--parser auto` for PDFs when installed |
| PyPDF baseline | `pipelines/parse_normalize/parser_adapter.py` | Still available as `--parser pypdf`; auto fallback is labeled `pypdf_baseline` |
| Table strategy | `pipelines/parse/table_extractor.py` | Implemented as strategy decision helper |

## L02 Chunk: Structure First, Then Context

| Lesson concept | Repository path | Runtime status |
|---|---|---|
| Structure-aware chunks | `pipelines/chunker/structure_aware.py` and `pipelines/parse_normalize/chunking.py` | Default classroom runtime |
| Contextual retrieval prefix | `pipelines/chunker/contextual.py` | Default chunks carry `context_prefix` |
| Late chunking | `pipelines/chunker/late_chunking.py` | Optional plan only; no heavyweight embedding model by default |
| Code AST chunking | `pipelines/chunker/code_ast.py` | Regex fallback helper; Tree-sitter remains production extension |

## L03 Evidence: Anchors Are Contract Data

| Lesson concept | Repository path | Runtime status |
|---|---|---|
| Evidence anchor schema | `contracts/data/evidence_anchor.schema.json` | Includes source identity, location, spans, heading path, parser capability |
| Anchor generation | `pipelines/parse_normalize/evidence_anchor.py` | Default runtime |
| Database fields | `infra/migrations/006_week07_ppt_alignment.sql` | Additive migration |

## L04 Quality: Gate Before Indexing

| Lesson concept | Repository path | Runtime status |
|---|---|---|
| Quality gate | `pipelines/parse_normalize/quality_gate.py` | Default runtime |
| Quality report dimensions | `pipelines/quality/report.py` | Default metrics projection |
| Drift detector | `pipelines/quality/drift_detector.py` | Deterministic helper for future regression checks |

## L05 Multimodal: Real Files, Optional Heavy ML

| Lesson concept | Repository path | Runtime status |
|---|---|---|
| Audio transcript processing | `pipelines/audio/process.py` | Sidecar-driven classroom runtime; Whisper is an optional upstream adapter |
| Video three-track model | `pipelines/video/pipeline.py` | Alignment helper; default runtime uses transcript/keyframe sidecars |
| CLIP-style embeddings | `pipelines/multimodal/clip_embed.py` | Optional dependency probe only |
| Real fixtures | `data/week07_media/` and `data/seed_manifests/manifest_week07_multimodal_v1.json` | Shipped classroom fixtures |

## Teaching Positioning

For Week07, the production direction is IDP-first, evidence-first, and multimodal-ready. The classroom route keeps everything runnable on Docker or Podman without requiring large OCR, ASR, VLM, or embedding models. When a dependency is missing, the code records the fallback explicitly instead of hiding it.
