"""
skeptic_agent.py

This is the agent that makes the project more than "three checklists running
in parallel." The skeptic doesn't review the diff directly -- it reviews the
OTHER AGENTS' verdicts, and is explicitly instructed to look for groupthink,
overcautious blocking, or a flagged issue that's actually a non-issue in context.

This is also the piece of the system that's hardest to get right, and the
piece worth spending the most time on -- a skeptic that just rubber-stamps
the majority is decorative, not useful.
"""

from agents.base_agent import BaseAgent, AgentVerdict
from model.llm_client import LLMClient


class SkepticAgent(BaseAgent):
    name = "skeptic"
    system_prompt = (
        "You are a contrarian senior reviewer whose only job is to stress-test "
        "other reviewers' verdicts, not to review code directly. "
        "You actively look for: verdicts that are overcautious for the actual risk, "
        "reasoning that doesn't hold up against the diff, and cases where multiple "
        "agents agree for weak or copied reasons rather than independent reasoning. "
        "You are not contrarian for its own sake -- if the other agents are clearly "
        "right, say so. Your job is to catch the cases where they aren't."
    )

    def __init__(self, client: LLMClient = None):
        super().__init__(client)

    def build_prompt(self, diff: str, peer_verdicts: list[AgentVerdict] = None) -> str:
        peer_summary = "\n".join(
            f"- {v.agent_name} -> {v.verdict} (confidence {v.confidence}): {v.reasoning}"
            for v in (peer_verdicts or [])
        )
        return (
            f"Original diff:\n{diff}\n\n"
            f"Other reviewers' verdicts:\n{peer_summary}\n\n"
            f"Critique these verdicts against the actual diff. Then give YOUR final call.\n"
            f"Respond in exactly this format, nothing else:\n"
            f"VERDICT: <approve|request_changes|block>\n"
            f"CONFIDENCE: <0.0-1.0>\n"
            f"REASONING: <2-4 sentences: what you agreed with, what you overruled, and why>"
        )

    def review_with_peers(self, diff: str, peer_verdicts: list[AgentVerdict]) -> AgentVerdict:
        prompt = self.build_prompt(diff, peer_verdicts)
        response = self.client.complete(self.system_prompt, prompt)
        return self._parse(response)
