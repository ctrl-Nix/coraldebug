"""
orchestrator.py

THE core design decision of this project lives here: how do 4 independent
agent opinions become ONE verdict?

Approach chosen: confidence-weighted vote, with the skeptic acting as a
tie-breaker / overrule mechanism rather than a 5th equal vote. Rationale,
written down here on purpose because "why this and not majority vote" is
exactly the kind of question you should be able to answer out loud:

  - Pure majority vote (3 of 4 agree -> verdict) sounds simple but breaks
    immediately: if security, performance, and architecture all flag the
    SAME root cause independently, that's 3 votes for one real issue, not
    3 independent signals. Confidence weighting + skeptic review catches
    correlated false-positives that plain majority vote can't.

  - Giving the skeptic an equal 5th vote would let it get outvoted by the
    same groupthink it exists to catch. Instead it reviews the other three
    verdicts directly and can OVERRULE them with justification, which is
    closer to how a real human tech lead resolves disagreeing reviewers.

  - Final severity ranking: block > request_changes > approve. A single
    "block" from ANY specialist agent (security in particular) is never
    silently averaged away by three "approve"s -- security blocks are a
    veto unless the skeptic explicitly overturns it with reasoning.
"""

import time
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from typing import List
from agents.base_agent import AgentVerdict
from agents.security_agent import SecurityAgent
from agents.performance_agent import PerformanceAgent
from agents.architecture_agent import ArchitectureAgent
from agents.skeptic_agent import SkepticAgent

VERDICT_SEVERITY = {"approve": 0, "request_changes": 1, "block": 2}


@dataclass
class FinalReview:
    final_verdict: str
    final_confidence: float
    specialist_verdicts: List[AgentVerdict]
    skeptic_verdict: AgentVerdict
    overruled: bool
    summary: str
    latency_s: float = 0.0


class ReviewOrchestrator:
    def __init__(self):
        self.security = SecurityAgent()
        self.performance = PerformanceAgent()
        self.architecture = ArchitectureAgent()
        self.skeptic = SkepticAgent()

    def run(self, diff: str) -> FinalReview:
        t0 = time.time()

        # Specialists are independent of each other by design (each only
        # sees the diff, not peer output), so they can run concurrently.
        # This is an I/O-bound wait on model calls, not CPU-bound work, so
        # a thread pool is the right tool here rather than multiprocessing.
        # Run benchmarks/run_benchmark.py against your local Ollama instance
        # to get real before/after numbers for your hardware -- don't trust
        # a number you didn't measure yourself on your own setup.
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [
                pool.submit(self.security.review, diff),
                pool.submit(self.performance.review, diff),
                pool.submit(self.architecture.review, diff),
            ]
            specialists = [f.result() for f in futures]

        skeptic_verdict = self.skeptic.review_with_peers(diff, specialists)

        final_verdict, overruled = self._resolve(specialists, skeptic_verdict)
        avg_confidence = sum(v.confidence for v in specialists + [skeptic_verdict]) / (
            len(specialists) + 1
        )

        summary = self._build_summary(specialists, skeptic_verdict, final_verdict, overruled)
        latency = time.time() - t0

        return FinalReview(
            final_verdict=final_verdict,
            final_confidence=round(avg_confidence, 2),
            specialist_verdicts=specialists,
            skeptic_verdict=skeptic_verdict,
            overruled=overruled,
            summary=summary,
            latency_s=round(latency, 2),
        )

    def _resolve(self, specialists: List[AgentVerdict], skeptic: AgentVerdict):
        worst_specialist = max(specialists, key=lambda v: VERDICT_SEVERITY[v.verdict])
        security_block = next(
            (v for v in specialists if v.agent_name == "security" and v.verdict == "block"),
            None,
        )

        # Security block is a veto unless the skeptic explicitly disagrees
        # with HIGHER confidence than the security agent's own confidence.
        if security_block and not (
            skeptic.verdict != "block" and skeptic.confidence > security_block.confidence
        ):
            return "block", False

        if security_block:
            # skeptic overruled the security block
            return skeptic.verdict, True

        # Otherwise: skeptic's verdict is the final call if it disagrees
        # with the specialist majority and is reasonably confident.
        specialist_majority = worst_specialist.verdict
        if skeptic.verdict != specialist_majority and skeptic.confidence >= 0.6:
            return skeptic.verdict, True

        return specialist_majority, False

    def _build_summary(self, specialists, skeptic, final_verdict, overruled) -> str:
        lines = [f"FINAL VERDICT: {final_verdict.upper()} (overruled by skeptic: {overruled})", ""]
        for v in specialists:
            lines.append(f"[{v.agent_name}] {v.verdict} ({v.confidence}) — {v.reasoning}")
        lines.append(f"[skeptic] {skeptic.verdict} ({skeptic.confidence}) — {skeptic.reasoning}")
        return "\n".join(lines)
