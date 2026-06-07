# Week07 Real Multimodal Parse Design

Week07 is the first real non-structured data engineering checkpoint. The goal is not to call an LLM on raw files. The goal is to turn raw PDF, image, audio, and video assets into governed retrieval units with source fingerprints, parser capability, evidence anchors, and quality gates.

## Design Principles

1. Raw media bytes are never treated as text.
2. Every extracted chunk must carry source identity, parser backend, parser capability, release lineage, and evidence anchor.
3. Heavy ML inference remains optional. The course path uses lightweight, reproducible tooling and sidecar artifacts that represent common enterprise upstream OCR/ASR output.
4. Week08 can index only chunks that are anchored, non-empty, not synthetic source fallback, and not blocked by media extraction errors.

## Modalities

| Modality | Real input | Parser backend | Evidence unit | Week08 handoff |
|---|---|---|---|---|
| PDF | `.pdf` bytes | `pypdf` | page + paragraph | allowed when text exists and page anchor exists |
| Image | `.png` bytes | `tesseract_ocr` or `ocr_sidecar` | object OCR text | allowed when OCR text exists |
| Audio | `.wav` bytes + transcript sidecar | `audio_transcript_sidecar` | utterance timestamp | allowed when transcript sidecar exists |
| Video | `.mp4` bytes + transcript/keyframe OCR sidecar | `video_ffmpeg_sidecar` | transcript timestamp + keyframe | allowed when transcript or keyframe evidence exists |

## Why Sidecars Are Valid Engineering Artifacts

In production, ASR/OCR is often a separate upstream service. The downstream data engineering pipeline should not pretend every learner machine can run a large ASR model. Instead, it should require that the raw media file and its derived OCR/ASR sidecar are versioned, checksummed, and audited together.

For classroom reliability, Week07 ships small course-synthetic assets under `data/week07_media/` and a manifest under `data/seed_manifests/manifest_week07_multimodal_v1.json`.

## Quality Gate

The quality gate blocks or warns on:

- missing chunks;
- missing evidence anchors;
- PDF page or bbox provenance gaps;
- synthetic source fallback;
- missing audio transcript sidecar;
- empty image OCR;
- video assets without transcript or keyframe OCR;
- suspected PII.

Fallback parser output is still useful for controlled demos, but it is not equivalent to real multimodal extraction.
