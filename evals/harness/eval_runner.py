"""Eval Harness — 回归评测执行器

对 RAG API 执行标准化评测，计算：
- Faithfulness（答案是否忠实于检索结果）
- Answer Relevance（答案与问题的相关性）
- Retrieval Precision@K
- Regression Pass Rate（对比历史基线）

使用方式:
    python -m evals.harness.eval_runner \
        --eval-set evals/sets/workspace_qa_v1.jsonl \
        --release-id dev-20260401-001 \
        --rag-api http://localhost:8000
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent


# ── Eval 数据结构 ─────────────────────────────────────────────────────────────

@dataclass
class EvalCase:
    """单个评测用例"""
    case_id: str
    query: str
    expected_answer: str | None = None          # 可选黄金答案
    expected_citations: list[str] = field(default_factory=list)
    product_line: str = "any"
    min_expected_score: float = 0.5
    tags: list[str] = field(default_factory=list)


@dataclass
class EvalResult:
    """单个用例的评测结果"""
    case_id: str
    query: str
    actual_answer: str
    actual_citations: list[str]
    confidence: float
    answer_grounded: bool
    trace_id: str
    retrieval_score: float = 0.0        # 检索精度
    faithfulness_score: float = 0.0     # 答案忠实度
    relevance_score: float = 0.0        # 答案相关性
    passed: bool = False
    error: str | None = None
    latency_ms: float = 0.0


@dataclass
class EvalRunSummary:
    eval_run_id: str
    release_id: str
    eval_set: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    error_cases: int
    avg_faithfulness: float
    avg_relevance: float
    avg_retrieval_precision: float
    regression_pass_rate: float
    avg_latency_ms: float
    run_at: str
    results: list[EvalResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        if self.total_cases == 0:
            return 0.0
        return self.passed_cases / self.total_cases


# ── 指标计算 ──────────────────────────────────────────────────────────────────

class MetricsCalculator:
    """
    简化版指标计算（不依赖 LLM judge，基于规则）。
    Week11 替换为基于 Claude 的 LLM-as-judge 评测。
    """

    def faithfulness(self, answer: str, retrieved_chunks: list[str]) -> float:
        """
        简化 faithfulness：检查答案中是否有检索内容的关键词。
        Week11: 用 Claude 判断答案是否忠实于检索结果。
        """
        if not retrieved_chunks or not answer:
            return 0.0

        all_chunk_words = set()
        for chunk in retrieved_chunks:
            all_chunk_words.update(chunk.lower().split())

        answer_words = set(answer.lower().split())
        overlap = len(answer_words & all_chunk_words)
        return min(overlap / max(len(answer_words), 1), 1.0)

    def answer_relevance(self, query: str, answer: str) -> float:
        """
        简化 relevance：基于词重叠。
        Week11: 用 Claude 判断答案是否回答了问题。
        """
        if not query or not answer:
            return 0.0
        q_words = set(query.lower().split())
        a_words = set(answer.lower().split())
        overlap = len(q_words & a_words)
        return min(overlap / max(len(q_words), 1), 1.0)

    def retrieval_precision(self, expected_citations: list[str], actual_citations: list[str]) -> float:
        """Precision@K：实际引用中有多少在预期引用集合中"""
        if not expected_citations or not actual_citations:
            return 1.0 if not expected_citations else 0.0
        hits = sum(1 for c in actual_citations if any(e in c for e in expected_citations))
        return hits / len(actual_citations)


# ── RAG API 客户端 ────────────────────────────────────────────────────────────

class RAGAPIClient:
    def __init__(self, base_url: str, timeout: float = 30.0):
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    async def query(self, case: EvalCase) -> dict:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base}/api/v1/query",
                json={
                    "query": case.query,
                    "product_line": case.product_line,
                    "top_k": 5,
                    "min_score": 0.0,
                },
            )
            resp.raise_for_status()
            return resp.json()


# ── Eval Runner ───────────────────────────────────────────────────────────────

class EvalRunner:
    def __init__(self, rag_api_url: str, release_id: str):
        self._client = RAGAPIClient(rag_api_url)
        self._metrics = MetricsCalculator()
        self._release_id = release_id

    def load_eval_set(self, path: Path) -> list[EvalCase]:
        """从 JSONL 文件加载评测用例"""
        cases = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                cases.append(EvalCase(
                    case_id=data["case_id"],
                    query=data["query"],
                    expected_answer=data.get("expected_answer"),
                    expected_citations=data.get("expected_citations", []),
                    product_line=data.get("product_line", "any"),
                    min_expected_score=data.get("min_expected_score", 0.5),
                    tags=data.get("tags", []),
                ))
        return cases

    async def run_case(self, case: EvalCase) -> EvalResult:
        t0 = time.time()
        try:
            response = await self._client.query(case)
            latency_ms = (time.time() - t0) * 1000

            answer = response.get("answer", "")
            citations = response.get("citations", [])
            confidence = response.get("confidence", 0.0)
            chunks_content = [c.get("content", "") for c in response.get("retrieved_chunks", [])]

            faithfulness = self._metrics.faithfulness(answer, chunks_content)
            relevance = self._metrics.answer_relevance(case.query, answer)
            retrieval_prec = self._metrics.retrieval_precision(
                case.expected_citations, citations
            )

            # 判断是否通过
            passed = (
                confidence >= case.min_expected_score
                and response.get("answer_grounded", False)
                and faithfulness >= 0.1   # 最低忠实度
            )

            return EvalResult(
                case_id=case.case_id,
                query=case.query,
                actual_answer=answer,
                actual_citations=citations,
                confidence=confidence,
                answer_grounded=response.get("answer_grounded", False),
                trace_id=response.get("trace_id", ""),
                retrieval_score=retrieval_prec,
                faithfulness_score=faithfulness,
                relevance_score=relevance,
                passed=passed,
                latency_ms=latency_ms,
            )

        except Exception as e:
            logger.error(f"Case {case.case_id} failed: {e}")
            return EvalResult(
                case_id=case.case_id,
                query=case.query,
                actual_answer="",
                actual_citations=[],
                confidence=0.0,
                answer_grounded=False,
                trace_id="",
                passed=False,
                error=str(e),
                latency_ms=(time.time() - t0) * 1000,
            )

    async def run(self, eval_set_path: Path, concurrency: int = 5) -> EvalRunSummary:
        import uuid as _uuid
        eval_run_id = f"eval-run-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        cases = self.load_eval_set(eval_set_path)
        logger.info(f"Running {len(cases)} eval cases (concurrency={concurrency})")

        results: list[EvalResult] = []
        semaphore = asyncio.Semaphore(concurrency)

        async def run_with_sem(case: EvalCase) -> EvalResult:
            async with semaphore:
                return await self.run_case(case)

        results = await asyncio.gather(*[run_with_sem(c) for c in cases])

        return self._summarize(eval_run_id, eval_set_path.name, list(results))

    def _summarize(
        self, eval_run_id: str, eval_set_name: str, results: list[EvalResult]
    ) -> EvalRunSummary:
        passed = [r for r in results if r.passed]
        failed = [r for r in results if not r.passed and not r.error]
        errored = [r for r in results if r.error]

        def avg(vals):
            return sum(vals) / len(vals) if vals else 0.0

        summary = EvalRunSummary(
            eval_run_id=eval_run_id,
            release_id=self._release_id,
            eval_set=eval_set_name,
            total_cases=len(results),
            passed_cases=len(passed),
            failed_cases=len(failed),
            error_cases=len(errored),
            avg_faithfulness=avg([r.faithfulness_score for r in results if not r.error]),
            avg_relevance=avg([r.relevance_score for r in results if not r.error]),
            avg_retrieval_precision=avg([r.retrieval_score for r in results if not r.error]),
            regression_pass_rate=len(passed) / max(len(results), 1),
            avg_latency_ms=avg([r.latency_ms for r in results]),
            run_at=datetime.now(timezone.utc).isoformat(),
            results=results,
        )

        self._print_summary(summary)
        return summary

    def _print_summary(self, s: EvalRunSummary):
        gate = "✅ PASS" if s.regression_pass_rate >= 0.8 else "❌ FAIL"
        print(f"""
{'='*60}
  EVAL RUN SUMMARY  {gate}
{'='*60}
  Run ID        : {s.eval_run_id}
  Release       : {s.release_id}
  Eval Set      : {s.eval_set}
  Total Cases   : {s.total_cases}
  Passed        : {s.passed_cases} ({s.pass_rate:.1%})
  Failed        : {s.failed_cases}
  Errors        : {s.error_cases}
  Faithfulness  : {s.avg_faithfulness:.3f}
  Relevance     : {s.avg_relevance:.3f}
  Retrieval P@K : {s.avg_retrieval_precision:.3f}
  Pass Rate     : {s.regression_pass_rate:.1%}
  Avg Latency   : {s.avg_latency_ms:.0f}ms
{'='*60}
""")

    def save_report(self, summary: EvalRunSummary, output_dir: Path):
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / f"{summary.eval_run_id}.json"
        data = asdict(summary)
        report_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        logger.info(f"Report saved: {report_path}")
        return report_path


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="OmniSupport Eval Runner")
    parser.add_argument("--eval-set", type=Path, required=True)
    parser.add_argument("--release-id", default="dev-local")
    parser.add_argument("--rag-api", default="http://localhost:8000")
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "evals" / "reports")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    runner = EvalRunner(args.rag_api, args.release_id)
    summary = asyncio.run(runner.run(args.eval_set, args.concurrency))
    runner.save_report(summary, args.output_dir)

    sys.exit(0 if summary.regression_pass_rate >= 0.8 else 1)


if __name__ == "__main__":
    main()
