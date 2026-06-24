"""
Tests for the orchestrator's resolution logic. These are deliberately written
against _resolve() directly (no LLM calls) so they run instantly and test the
actual decision logic, not model output variance.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent import AgentVerdict
from orchestrator import ReviewOrchestrator
from model.llm_client import LLMResponse


def make_verdict(agent_name, verdict, confidence, reasoning="test"):
    fake_response = LLMResponse(text="", source="test", model="test", latency_s=0.0)
    return AgentVerdict(
        agent_name=agent_name,
        verdict=verdict,
        confidence=confidence,
        reasoning=reasoning,
        raw_response=fake_response,
    )


def test_security_block_is_veto_by_default():
    orch = ReviewOrchestrator()
    specialists = [
        make_verdict("security", "block", 0.9, "hardcoded credential found"),
        make_verdict("performance", "approve", 0.6),
        make_verdict("architecture", "approve", 0.6),
    ]
    skeptic = make_verdict("skeptic", "approve", 0.5, "seems fine actually")

    final_verdict, overruled = orch._resolve(specialists, skeptic)

    assert final_verdict == "block"
    assert overruled is False


def test_skeptic_can_overrule_security_block_with_higher_confidence():
    orch = ReviewOrchestrator()
    specialists = [
        make_verdict("security", "block", 0.4, "looks suspicious but unsure"),
        make_verdict("performance", "approve", 0.6),
        make_verdict("architecture", "approve", 0.6),
    ]
    skeptic = make_verdict(
        "skeptic", "approve", 0.85, "that string is a test fixture, not a real secret"
    )

    final_verdict, overruled = orch._resolve(specialists, skeptic)

    assert final_verdict == "approve"
    assert overruled is True


def test_skeptic_does_not_overrule_majority_with_low_confidence():
    orch = ReviewOrchestrator()
    specialists = [
        make_verdict("security", "approve", 0.7),
        make_verdict("performance", "request_changes", 0.6, "N+1 query"),
        make_verdict("architecture", "approve", 0.6),
    ]
    skeptic = make_verdict("skeptic", "approve", 0.4, "weakly disagree")

    final_verdict, overruled = orch._resolve(specialists, skeptic)

    assert final_verdict == "request_changes"
    assert overruled is False


def test_skeptic_overrules_majority_with_high_confidence():
    orch = ReviewOrchestrator()
    specialists = [
        make_verdict("security", "approve", 0.7),
        make_verdict("performance", "request_changes", 0.55, "minor nit"),
        make_verdict("architecture", "approve", 0.6),
    ]
    skeptic = make_verdict(
        "skeptic", "approve", 0.8, "the performance concern doesn't hold up against the diff"
    )

    final_verdict, overruled = orch._resolve(specialists, skeptic)

    assert final_verdict == "approve"
    assert overruled is True


def test_clean_approve_with_no_disagreement():
    orch = ReviewOrchestrator()
    specialists = [
        make_verdict("security", "approve", 0.9),
        make_verdict("performance", "approve", 0.9),
        make_verdict("architecture", "approve", 0.9),
    ]
    skeptic = make_verdict("skeptic", "approve", 0.9, "agree with all three")

    final_verdict, overruled = orch._resolve(specialists, skeptic)

    assert final_verdict == "approve"
    assert overruled is False
