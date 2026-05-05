#!/usr/bin/env python3
"""LLM Provider Benchmark — compare identity verification across providers.

Usage::

    # Full benchmark (requires DEEPSEEK_API_KEY, KIMI_API_KEY, DASHSCOPE_API_KEY)
    python scripts/benchmark_llm.py

    # Single provider
    python scripts/benchmark_llm.py --provider deepseek

    # Dry run (synthetic data, no API calls)
    python scripts/benchmark_llm.py --dry-run

Output: Markdown table comparing providers on accuracy, confidence, latency.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clawithme.crawler.base import Profile
from clawithme.signals.llm_verifier import (
    LLMProvider,
    LLMVerifier,
    _call_provider,
    _parse_structured_response,
    discover_providers,
)

# ── Test Cases ───────────────────────────────────────────────────

@dataclass
class TestCase:
    name: str
    profile_a: Profile
    profile_b: Profile
    expected: str  # "SAME" or "DIFFERENT" or "BORDERLINE"


# Synthetic test cases — no real data, just patterns
CASES: list[TestCase] = []

# Populate test cases
def _p(site_id: str, **kw) -> Profile:
    defaults = dict(site_name=site_id, url=f"https://{site_id}.com/u", username=site_id)
    defaults.update(kw)
    return Profile(site_id=site_id, **defaults)


CASES.append(TestCase(
    name="clear_match",
    profile_a=_p("github", display_name="Sindre Sorhus", bio="Full-time open-sourcerer", location="Thailand"),
    profile_b=_p("gitlab", display_name="Sindre Sorhus", bio="Maker of awesome open-source tools", location="Thailand"),
    expected="SAME",
))

CASES.append(TestCase(
    name="clear_mismatch",
    profile_a=_p("github", display_name="John Smith", bio="Software engineer at Google", location="New York, USA"),
    profile_b=_p("zhihu", display_name="张伟", bio="前端开发工程师", location="Beijing, China"),
    expected="DIFFERENT",
))

CASES.append(TestCase(
    name="affix_variant",
    profile_a=_p("github", display_name="Alice Chen", bio="Python developer", location="San Francisco"),
    profile_b=_p("devto", display_name="Alice C.", bio="Backend engineer, Python enthusiast", location="SF Bay Area"),
    expected="SAME",
))

CASES.append(TestCase(
    name="same_name_diff_field",
    profile_a=_p("github", display_name="Alex", bio="Game developer, Unity/C#", location="London"),
    profile_b=_p("gitlab", display_name="Alex", bio="Data scientist, Python/ML", location="Berlin"),
    expected="BORDERLINE",
))

CASES.append(TestCase(
    name="common_short_name",
    profile_a=_p("github", display_name="Max", bio="Frontend developer", location="Amsterdam"),
    profile_b=_p("stackoverflow", display_name="Max", bio="Backend developer, Java", location="Tokyo"),
    expected="DIFFERENT",
))


# ── Benchmark ────────────────────────────────────────────────────


@dataclass
class BenchmarkResult:
    provider: str
    model: str
    total: int = 0
    correct: int = 0
    avg_confidence: float = 0.0
    avg_latency_ms: int = 0
    per_case: list[dict] = None

    def __post_init__(self):
        if self.per_case is None:
            self.per_case = []


def run_benchmark(
    providers: list[LLMProvider],
    cases: list[TestCase],
    dry_run: bool = False,
) -> list[BenchmarkResult]:
    results: list[BenchmarkResult] = []

    for provider in providers:
        result = BenchmarkResult(provider=provider.name, model=provider.model)
        confidences: list[float] = []
        latencies: list[int] = []

        for case in cases:
            if dry_run:
                # Simulate with deterministic fake results
                is_same = case.expected == "SAME"
                confidence = 0.85 if is_same else 0.80
                latency = 500
                reason = f"[dry-run] {case.expected}"
            else:
                prompt = LLMVerifier._build_pair_prompt(case.profile_a, case.profile_b)
                t0 = time.monotonic()
                raw = _call_provider(
                    provider,
                    [{"role": "user", "content": prompt}],
                    max_tokens=128,
                )
                latency = int((time.monotonic() - t0) * 1000)
                if raw:
                    is_same, confidence, reason = _parse_structured_response(raw)
                else:
                    is_same, confidence, reason = False, 0.0, "API_FAILED"

            # Determine correctness
            if case.expected == "BORDERLINE":
                correct = None  # not scored
            else:
                expected_bool = case.expected == "SAME"
                correct = (is_same == expected_bool)

            result.total += 1
            if correct is True:
                result.correct += 1
            confidences.append(confidence)
            latencies.append(latency)

            result.per_case.append({
                "case": case.name,
                "expected": case.expected,
                "is_same": is_same,
                "confidence": round(confidence, 2),
                "latency_ms": latency,
                "reason": reason[:100],
                "correct": "✓" if correct is True else ("✗" if correct is False else "~"),
            })

        if confidences:
            result.avg_confidence = round(sum(confidences) / len(confidences), 2)
        if latencies:
            result.avg_latency_ms = int(sum(latencies) / len(latencies))

        results.append(result)

    return results


# ── Output ───────────────────────────────────────────────────────


def print_results(results: list[BenchmarkResult], dry_run: bool = False):
    mode = "DRY-RUN" if dry_run else "LIVE"
    print(f"\n## LLM Provider Benchmark — {mode}\n")
    print(f"  Test cases: {len(CASES)}")

    # Summary table
    print("\n### Summary\n")
    print(f"| {'Provider':<12s} | {'Model':<18s} | {'Accuracy':>8s} | {'Avg Conf':>8s} | {'Avg Latency':>12s} |")
    print(f"|{'-'*13}|{'-'*19}|{'-'*10}|{'-'*10}|{'-'*14}|")

    for r in results:
        acc = f"{r.correct}/{r.total - sum(1 for c in r.per_case if c['expected'] == 'BORDERLINE')}" if r.total > 0 else "N/A"
        conf = f"{r.avg_confidence:.2f}" if r.total > 0 else "—"
        lat = f"{r.avg_latency_ms} ms" if r.total > 0 else "—"
        print(f"| {r.provider:<12s} | {r.model:<18s} | {acc:>8s} | {conf:>8s} | {lat:>12s} |")

    # Per-case detail
    if results:
        print("\n### Per-Case Detail\n")

        # Header
        case_names = [c["case"] for c in results[0].per_case]
        header = f"| {'Case':<22s} |" + "|".join(f" {p.provider:<14s} " for p in results) + "|"
        sep = f"|{'-'*23}|" + "|".join("-" * 16 for _ in results) + "|"
        print(header)
        print(sep)

        for i, case_name in enumerate(case_names):
            cells = [case_name]
            for r in results:
                c = r.per_case[i]
                cell = f"{c['correct']} {c['confidence']:.0%}"
                cells.append(cell)
            print(f"| {'|'.join(f'{cell:<22s}' if j == 0 else f' {cell:<14s} ' for j, cell in enumerate(cells))} |")

    print()


# ── Main ─────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="LLM Provider Benchmark")
    parser.add_argument("--provider", help="Only run one provider (deepseek/kimi/dashscope)")
    parser.add_argument("--dry-run", action="store_true", help="Synthetic data, no API calls")
    args = parser.parse_args()

    providers = discover_providers()
    if not providers:
        if args.dry_run:
            # Create fake providers for dry-run
            providers = [
                LLMProvider(name="deepseek", api_key="fake", base_url="", model="deepseek-chat", priority=0),
                LLMProvider(name="kimi", api_key="fake", base_url="", model="moonshot-v1-8k", priority=1),
                LLMProvider(name="dashscope", api_key="fake", base_url="", model="qwen-plus", priority=2),
            ]
        else:
            print("❌ No LLM providers configured. Set DEEPSEEK_API_KEY, KIMI_API_KEY, or DASHSCOPE_API_KEY.")
            print("   Or run with --dry-run for synthetic benchmark.")
            sys.exit(1)

    if args.provider:
        providers = [p for p in providers if p.name == args.provider]
        if not providers:
            print(f"❌ Provider '{args.provider}' not configured.")
            sys.exit(1)

    print(f"🔬 Running benchmark with {len(providers)} provider(s): "
          f"{', '.join(p.name for p in providers)}")
    if args.dry_run:
        print("   (dry-run mode — synthetic data, no API calls)")

    results = run_benchmark(providers, CASES, dry_run=args.dry_run)
    print_results(results, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
