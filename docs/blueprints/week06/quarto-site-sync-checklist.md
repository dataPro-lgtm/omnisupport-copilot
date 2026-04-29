# Week06 Quarto Site Sync Checklist

No Quarto course-site source is modified in this project branch. The course site should link to the following real repo files after Week06 code is merged.

## Week Page Links

- Blueprint: `docs/blueprints/week06/week06-data-factory-blueprint.md`
- Asset graph: `docs/blueprints/week06/week06-asset-graph.md`
- Partition/backfill strategy: `docs/blueprints/week06/week06-partition-backfill-strategy.md`
- Run evidence spec: `docs/blueprints/week06/week06-run-evidence-spec.md`
- Runbook: `runbooks/week06-data-factory.md`
- Evidence schema: `contracts/run_evidence/week06_run_evidence.schema.json`

## Lab Commands

Executable from the repo root through Docker devbox:

```bash
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  pytest tests/contract/test_week06_run_evidence_schema.py

docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox \
  python -m pipelines.data_factory.backfill_plan --partition 2026-04-17 --mode dry-run
```

Podman uses the same commands with `podman compose`.

## Assignment Artifacts

Students can submit:

- Generated backfill dry-run plan under `reports/week06/backfill/`.
- Generated run evidence JSON under `reports/week06/run_evidence/`.
- Generated asset check summary under `reports/week06/asset_checks_summary.md`.

Generated runtime artifacts are intentionally ignored by Git.
