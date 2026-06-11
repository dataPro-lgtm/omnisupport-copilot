# Week07 Quality Gate Spec

## Checks

- Metadata completeness.
- Anchor coverage.
- Empty chunk count.
- Orphan chunk count.
- Orphan anchor count.
- PDF page number presence.
- PDF bbox missing reason.
- Fallback parser usage.
- Synthetic source fallback usage.
- PII heuristic sample.
- Quality report projection: completeness, noise, evidence, and coherence.

## Status Rules

- `pass`: no errors and no warnings.
- `warn`: no blocking errors, but fallback, synthetic source, metadata, or PII warnings exist.
- `fail`: no chunks, empty chunks, missing anchors, orphan links, or PDF evidence defects.

## Week8 Ready

`week8_ready=true` only when:

- At least one chunk exists.
- No blocking errors exist.
- No synthetic-source fallback chunks exist.
- Every indexable chunk has at least one evidence anchor.

Week08 must still filter by `allowed_for_indexing=true` at build time.

## PPT Alignment

The Week07 deck describes four quality dimensions:

- `completeness_score`: whether required metadata and output coverage are complete.
- `noise_score`: whether output avoids empty chunks and excessive fallback noise.
- `evidence_score`: whether chunks have usable evidence anchors.
- `coherence_score`: whether blocking structural errors are absent.

The runtime gate keeps the original pass/warn/fail behavior and adds these metrics to the report so classroom demos can explain both the operational gate and the higher-level quality framework.
