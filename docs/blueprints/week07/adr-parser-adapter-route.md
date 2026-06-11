# ADR: Parser Adapter Route

## Decision

Week07 uses a parser adapter with these classroom-safe modes:

- `auto`
- `idp`
- `marker`
- `docling`
- `unstructured`
- `fallback`
- `pypdf`
- `pypdf_baseline`
- `ocr`
- `media`

`auto` routes PDF assets toward an IDP-first path (`marker`, then `docling`) and text/HTML-like assets toward Unstructured. If the optional IDP dependency is unavailable, the adapter falls back to `pypdf_baseline` and records the reason in parser capability warnings. Explicit `--parser pypdf` still exists as a teaching baseline, but it is not positioned as the production parser.

## Why

Course environments vary. Some enterprise machines can run Docker/Podman but cannot install native parser dependencies. A hard dependency on Marker, Docling, OCR, ASR, or VLM packages would make Week07 fragile for students. The code therefore keeps the production route visible and optional while preserving a deterministic classroom fallback.

## Consequences

- The fallback path is deterministic and testable.
- Parser capability is written into every section and anchor.
- PDF baseline fallback is visible as `pypdf_baseline`, so students do not confuse it with the IDP production route.
- Week08 can reject or down-rank fallback outputs if the course later enables stricter indexing gates.
- Real Marker/Docling/Unstructured integration remains an instructor-scale upgrade, not a separate architecture.
