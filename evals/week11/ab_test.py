"""A/B test utilities for eval scores without heavyweight scipy dependencies."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path


def required_sample_size(effect: float = 0.05, alpha: float = 0.05, power: float = 0.8) -> int:
    """Classroom sample-size anchor for RAG eval A/B tests.

    The Week11 deck teaches practical anchors instead of a statistics package:
    large effect (~10%) needs roughly 80 samples, medium effect (~5%) needs
    roughly 200, and small effect (~2%) needs roughly 800. Production teams
    should replace this helper with a domain-specific power analysis.
    """

    _ = (alpha, power)
    if effect >= 0.10:
        return 80
    if effect >= 0.05:
        return 200
    if effect >= 0.02:
        return 800
    return math.ceil(800 * (0.02 / max(effect, 1e-9)) ** 2)


def compare(a: list[float], b: list[float]) -> dict:
    if len(a) < 2 or len(b) < 2:
        raise ValueError("A/B comparison needs at least two samples per arm")
    diff = statistics.mean(b) - statistics.mean(a)
    t_stat = _welch_t(a, b)
    p_ttest = _two_sided_normal_p(abs(t_stat))
    u_stat, p_mwu = _mann_whitney(a, b)
    significant = p_ttest < 0.05 and p_mwu < 0.05
    return {
        "mean_a": round(statistics.mean(a), 6),
        "mean_b": round(statistics.mean(b), 6),
        "diff": round(diff, 6),
        "p_ttest_approx": round(p_ttest, 6),
        "mann_whitney_u": round(u_stat, 6),
        "p_mwu_approx": round(p_mwu, 6),
        "significant": significant,
        "recommendation": "ship_B" if significant and diff > 0 else "keep_A" if significant else "need_more_data",
    }


def _welch_t(a: list[float], b: list[float]) -> float:
    var_a = statistics.variance(a)
    var_b = statistics.variance(b)
    return (statistics.mean(b) - statistics.mean(a)) / math.sqrt(var_a / len(a) + var_b / len(b))


def _two_sided_normal_p(z: float) -> float:
    return math.erfc(z / math.sqrt(2))


def _mann_whitney(a: list[float], b: list[float]) -> tuple[float, float]:
    ranked = sorted([(value, "a") for value in a] + [(value, "b") for value in b], key=lambda item: item[0])
    ranks: list[tuple[float, str]] = []
    idx = 0
    while idx < len(ranked):
        end = idx + 1
        while end < len(ranked) and ranked[end][0] == ranked[idx][0]:
            end += 1
        avg_rank = (idx + 1 + end) / 2
        ranks.extend((avg_rank, group) for _, group in ranked[idx:end])
        idx = end
    rank_b = sum(rank for rank, group in ranks if group == "b")
    n1, n2 = len(a), len(b)
    u_b = rank_b - n2 * (n2 + 1) / 2
    mean_u = n1 * n2 / 2
    sd_u = math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12)
    p = _two_sided_normal_p(abs((u_b - mean_u) / max(sd_u, 1e-9)))
    return u_b, p


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare two eval score arrays")
    parser.add_argument("--a", type=Path)
    parser.add_argument("--b", type=Path)
    parser.add_argument("--effect", type=float, default=0.05)
    args = parser.parse_args(argv)
    print(f"required_sample_size={required_sample_size(effect=args.effect)}")
    if args.a and args.b:
        a = json.loads(args.a.read_text(encoding="utf-8"))
        b = json.loads(args.b.read_text(encoding="utf-8"))
        print(json.dumps(compare(a, b), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
