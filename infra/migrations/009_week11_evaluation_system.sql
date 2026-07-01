-- Week11 evaluation system tables.
-- Safe to run repeatedly. Extends the early eval skeleton without changing
-- Week01-Week10 operational tables.

CREATE TABLE IF NOT EXISTS eval_dataset_manifest (
    dataset_id       TEXT NOT NULL,
    version          TEXT NOT NULL,
    sample_count     INTEGER NOT NULL,
    categories       JSONB NOT NULL,
    digest           TEXT NOT NULL,
    generated_from   JSONB DEFAULT '[]'::jsonb,
    created_at       TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (dataset_id, version)
);

ALTER TABLE eval_run
    ADD COLUMN IF NOT EXISTS eval_dataset_id TEXT,
    ADD COLUMN IF NOT EXISTS eval_dataset_version TEXT,
    ADD COLUMN IF NOT EXISTS eval_dataset_digest TEXT,
    ADD COLUMN IF NOT EXISTS avg_context_precision DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS avg_context_recall DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS avg_answer_correctness DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS avg_semantic_similarity DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS adversarial_pass_rate DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS safety_pass_rate DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS latency_p50_ms DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS latency_p99_ms DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS cost_per_query_usd DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS gate_status TEXT,
    ADD COLUMN IF NOT EXISTS gate_reasons JSONB DEFAULT '[]'::jsonb;

ALTER TABLE eval_case_result
    ADD COLUMN IF NOT EXISTS category TEXT,
    ADD COLUMN IF NOT EXISTS context_precision DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS context_recall DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS answer_correctness DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS semantic_similarity DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS safety_pass BOOLEAN,
    ADD COLUMN IF NOT EXISTS failure_reasons JSONB DEFAULT '[]'::jsonb;

CREATE TABLE IF NOT EXISTS judge_calibration_report (
    calibration_id       TEXT PRIMARY KEY,
    judge_prompt_version TEXT NOT NULL,
    calibration_set      TEXT NOT NULL,
    sample_count         INTEGER NOT NULL,
    cohen_kappa          DOUBLE PRECISION,
    pearson_r            DOUBLE PRECISION,
    mae                  DOUBLE PRECISION,
    top_k_overlap        DOUBLE PRECISION,
    trust_level          TEXT NOT NULL,
    created_at           TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS business_slo_snapshot (
    slo_snapshot_id TEXT PRIMARY KEY,
    release_id      TEXT NOT NULL,
    domain          TEXT NOT NULL,
    metrics         JSONB NOT NULL,
    status          TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_eval_run_dataset
    ON eval_run (eval_dataset_id, eval_dataset_version);

CREATE INDEX IF NOT EXISTS idx_eval_case_category
    ON eval_case_result (category);

