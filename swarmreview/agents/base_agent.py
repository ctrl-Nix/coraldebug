"""
base_agent.py

Every review agent is just: a persona (system prompt) + a structured
opinion format. Keeping this contract tiny is what makes the debate/voting
step in orchestrator.py possible -- agents that ramble in free text can't
be aggregated.
"""

from dataclasses import dataclass, field
from typing import List
from model.llm_client import LLMClient, LLMResponse


@dataclass
class AgentVerdict:
    agent_name: str
    verdict: str          # "approve" | "request_changes" | "block"
    confidence: float      # 0.0 - 1.0, self-reported
    reasoning: str
    raw_response: LLMResponse


class BaseAgent:
    name: str = "base"
    system_prompt: str = "You are a code review agent."

    def __init__(self, client: LLMClient = None):
        self.client = client or LLMClient()

    def build_prompt(self, diff: str) -> str:
        return (
            f"Review the following git diff strictly from your assigned lens.\n\n"
            f"DIFF:\n{diff}\n\n"
            f"Respond in exactly this format, nothing else:\n"
            f"VERDICT: <approve|request_changes|block>\n"
            f"CONFIDENCE: <0.0-1.0>\n"
            f"REASONING: <2-4 sentences, specific to the diff, no generic advice>"
        )

    def review(self, diff: str) -> AgentVerdict:
        prompt = self.build_prompt(diff)
        response = self.client.complete(self.system_prompt, prompt)
        return self._parse(response)

    def _parse(self, response: LLMResponse) -> AgentVerdict:
        verdict, confidence, reasoning = "request_changes", 0.5, response.text.strip()
        for line in response.text.splitlines():
            line = line.strip()
            if line.upper().startswith("VERDICT:"):
                verdict = line.split(":", 1)[1].strip().lower()
            elif line.upper().startswith("CONFIDENCE:"):
                try:
                    confidence = float(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
            elif line.upper().startswith("REASONING:"):
                reasoning = line.split(":", 1)[1].strip()
        return AgentVerdict(
            agent_name=self.name,
            verdict=verdict,
            confidence=confidence,
            reasoning=reasoning,
            raw_response=response,
        )
