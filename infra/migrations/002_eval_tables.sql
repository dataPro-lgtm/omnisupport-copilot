-- Migration 002: Eval Run 记录表
-- 执行时机: Week11 接入 eval harness 时手动执行

CREATE TABLE IF NOT EXISTS eval_run (
    eval_run_id         TEXT PRIMARY KEY,
    release_id          TEXT NOT NULL,
    eval_set            TEXT NOT NULL,
    total_cases         INT DEFAULT 0,
    passed_cases        INT DEFAULT 0,
    failed_cases        INT DEFAULT 0,
    error_cases         INT DEFAULT 0,
    avg_faithfulness    DOUBLE PRECISION,
    avg_relevance       DOUBLE PRECISION,
    avg_retrieval_precision DOUBLE PRECISION,
    regression_pass_rate    DOUBLE PRECISION,
    avg_latency_ms      DOUBLE PRECISION,
    run_at              TIMESTAMPTZ DEFAULT NOW(),
    report_path         TEXT
);

CREATE INDEX IF NOT EXISTS idx_eval_run_release ON eval_run (release_id);
CREATE INDEX IF NOT EXISTS idx_eval_run_at ON eval_run (run_at DESC);

CREATE TABLE IF NOT EXISTS eval_case_result (
    result_id           TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    eval_run_id         TEXT REFERENCES eval_run(eval_run_id),
    case_id             TEXT NOT NULL,
    query               TEXT,
    actual_answer       TEXT,
    confidence          DOUBLE PRECISION,
    answer_grounded     BOOLEAN,
    faithfulness_score  DOUBLE PRECISION,
    relevance_score     DOUBLE PRECISION,
    retrieval_score     DOUBLE PRECISION,
    passed              BOOLEAN DEFAULT FALSE,
    error               TEXT,
    latency_ms          DOUBLE PRECISION,
    trace_id            TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_eval_case_run ON eval_case_result (eval_run_id);
CREATE INDEX IF NOT EXISTS idx_eval_case_passed ON eval_case_result (passed);
