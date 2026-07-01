"""Week11 RAGAS-compatible eval runner.

This classroom runner computes deterministic proxy metrics with the same
diagnostic shape as RAGAS: retrieval, generation, and overall answer quality.
It can run against a local predictions fixture or a running `/rag/answer` API.
"""

from evals.week11.runner import main


if __name__ == "__main__":
    raise SystemExit(main())

