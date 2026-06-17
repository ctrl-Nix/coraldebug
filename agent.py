"""
CoralDebug Multi-Agent Pipeline
--------------------------------
Three specialized agents that hand off structured outputs to each other,
instead of one mega-prompt:

  RetrieverAgent  -> pulls raw data from Sentry / GitHub / Slack via Coral
  DiagnosisAgent  -> takes that data, returns structured root-cause JSON
  FixAgent        -> takes the diagnosis, returns code fixes + confidence

Each agent has a single responsibility and a typed input/output contract,
so the pipeline can be tested, swapped, or extended one stage at a time.
"""

import json
import os
import subprocess
import pathlib
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY not set. Run: export GROQ_API_KEY='your-key-here' "
        "(or put it in a .env file — see README)."
    )

client = Groq(api_key=GROQ_API_KEY)
MODEL = "llama-3.3-70b-versatile"


# ---------------------------------------------------------------------------
# Shared data contracts between agents
# ---------------------------------------------------------------------------

@dataclass
class RawTelemetry:
    sentry: str
    github: str
    slack: str


@dataclass
class Diagnosis:
    error_title: str
    root_cause: str
    affected_repo: str
    severity: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class FixSuggestion:
    error_title: str
    suggested_fix: str
    confidence: float
    reasoning: str


@dataclass
class TriageResult:
    priority_rank: int
    error_title: str
    urgency_score: float
    action: str


# ---------------------------------------------------------------------------
# Agent 1: Retriever — owns all I/O with external sources
# ---------------------------------------------------------------------------

class RetrieverAgent:
    """Pulls raw telemetry from Sentry, GitHub, and Slack via Coral SQL."""

    def _run_coral(self, query: str) -> str:
        try:
            result = subprocess.run(
                ["coral", "sql", query, "--format", "json"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return f"[coral error] {result.stderr.strip()}"
            return result.stdout
        except FileNotFoundError:
            return "[coral not installed — see README setup]"
        except subprocess.TimeoutExpired:
            return "[coral query timed out]"

    def fetch(self) -> RawTelemetry:
        sentry = self._run_coral(
            "SELECT title, level, status, project FROM sentry.issues LIMIT 10"
        )
        github = self._run_coral(
            "SELECT name, open_issues_count, language FROM github.repositories LIMIT 5"
        )
        slack = self._run_coral(
            "SELECT id, name FROM slack.channels LIMIT 5"
        )
        return RawTelemetry(sentry=sentry, github=github, slack=slack)


# ---------------------------------------------------------------------------
# Agent 2: Diagnosis — focused only on root-cause analysis
# ---------------------------------------------------------------------------

class DiagnosisAgent:
    """Takes raw telemetry, returns structured root-cause diagnoses only.
    Does NOT suggest fixes — that's FixAgent's job."""

    SYSTEM_PROMPT = (
        "You are a root-cause analysis specialist. Given Sentry errors, "
        "GitHub repo metadata, and Slack channel context, identify the "
        "likely root cause of each error and which repo is affected. "
        "Do NOT propose fixes. "
        "Respond ONLY with valid JSON: a list of objects with keys "
        "error_title, root_cause, affected_repo, severity."
    )

    def diagnose(self, telemetry: RawTelemetry) -> list[Diagnosis]:
        user_prompt = (
            f"SENTRY ERRORS:\n{telemetry.sentry}\n\n"
            f"GITHUB REPOS:\n{telemetry.github}\n\n"
            f"SLACK CHANNELS:\n{telemetry.slack}\n"
        )
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1200,
        )
        content = response.choices[0].message.content
        return self._parse(content)

    def _parse(self, content: str) -> list[Diagnosis]:
        try:
            data = json.loads(content)
            items = data if isinstance(data, list) else data.get("diagnoses", [])
        except json.JSONDecodeError:
            # Model didn't return clean JSON — fall back to a single
            # diagnosis carrying the raw text, so the pipeline never crashes.
            return [
                Diagnosis(
                    error_title="unparsed",
                    root_cause=content,
                    affected_repo="unknown",
                    severity="unknown",
                )
            ]
        return [
            Diagnosis(
                error_title=item.get("error_title", "unknown"),
                root_cause=item.get("root_cause", ""),
                affected_repo=item.get("affected_repo", "unknown"),
                severity=item.get("severity", "unknown"),
                raw=item,
            )
            for item in items
        ]


# ---------------------------------------------------------------------------
# Agent 3: Fix — focused only on remediation, consumes Diagnosis objects
# ---------------------------------------------------------------------------

class FixAgent:
    """Takes structured diagnoses and proposes concrete fixes with a
    confidence score, so a human can triage what to trust vs. verify."""

    SYSTEM_PROMPT = (
        "You are a senior engineer proposing fixes. Given a root-cause "
        "diagnosis, suggest a concrete code-level or config-level fix, "
        "explain your reasoning briefly, and give a confidence score "
        "from 0.0 to 1.0 based on how certain you are without seeing "
        "the actual source code. "
        "Respond ONLY with valid JSON: an object with keys "
        "suggested_fix, confidence, reasoning."
    )

    def propose(self, diagnosis: Diagnosis) -> FixSuggestion:
        user_prompt = (
            f"Error: {diagnosis.error_title}\n"
            f"Root cause: {diagnosis.root_cause}\n"
            f"Affected repo: {diagnosis.affected_repo}\n"
            f"Severity: {diagnosis.severity}\n"
        )
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=500,
        )
        content = response.choices[0].message.content
        return self._parse(diagnosis.error_title, content)

    def _parse(self, error_title: str, content: str) -> FixSuggestion:
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return FixSuggestion(
                error_title=error_title,
                suggested_fix=content,
                confidence=0.0,
                reasoning="Model did not return structured JSON.",
            )
        return FixSuggestion(
            error_title=error_title,
            suggested_fix=data.get("suggested_fix", ""),
            confidence=float(data.get("confidence", 0.0)),
            reasoning=data.get("reasoning", ""),
        )


# ---------------------------------------------------------------------------
# Agent 4: Triage — focused on ranking diagnoses by urgency
# ---------------------------------------------------------------------------

class TriageAgent:
    """Ranks all diagnosed issues by urgency so engineers know what to fix first."""

    SYSTEM_PROMPT = (
        "You are a site reliability triage specialist. Given a list of diagnosed errors "
        "with root causes and fix confidence scores, rank them by urgency. "
        "Respond ONLY with valid JSON: a list sorted by priority (1 = most urgent), "
        "each object having keys: priority_rank, error_title, urgency_score (0.0 to 1.0), "
        "action ('fix-now', 'monitor', or 'investigate')."
    )

    def rank(self, diagnoses: list[Diagnosis], fixes: list[FixSuggestion]) -> list[TriageResult]:
        pairs = [
            {
                "error": d.error_title,
                "severity": d.severity,
                "root_cause": d.root_cause,
                "fix_confidence": f.confidence,
            }
            for d, f in zip(diagnoses, fixes)
        ]
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(pairs)},
            ],
            max_tokens=800,
        )
        content = response.choices[0].message.content
        return self._parse(content)

    def _parse(self, content: str) -> list[TriageResult]:
        try:
            data = json.loads(content)
            items = data if isinstance(data, list) else data.get("triage", [])
        except json.JSONDecodeError:
            return []
        
        return [
            TriageResult(
                priority_rank=int(item.get("priority_rank", 999)),
                error_title=item.get("error_title", "unknown"),
                urgency_score=float(item.get("urgency_score", 0.0)),
                action=item.get("action", "investigate"),
            )
            for item in items
        ]


# ---------------------------------------------------------------------------
# Pipeline orchestration — wires the three agents together
# ---------------------------------------------------------------------------

def run_pipeline() -> None:
    print("CoralDebug Multi-Agent Pipeline starting...")

    retriever = RetrieverAgent()
    diagnoser = DiagnosisAgent()
    fixer = FixAgent()
    triager = TriageAgent()

    print("[RetrieverAgent] Pulling Sentry + GitHub + Slack data...")
    telemetry = retriever.fetch()

    print("[DiagnosisAgent] Identifying root causes...")
    diagnoses = diagnoser.diagnose(telemetry)

    print(f"[FixAgent] Proposing fixes for {len(diagnoses)} issue(s)...")
    fixes = [fixer.propose(d) for d in diagnoses]

    print("[TriageAgent] Ranking issues by urgency...")
    triage_results = triager.rank(diagnoses, fixes)

    print("=" * 60)
    print("CORALDEBUG MULTI-AGENT REPORT")
    print("=" * 60)
    report_lines = ["CORALDEBUG MULTI-AGENT REPORT", "=" * 60]

    for d, f in zip(diagnoses, fixes):
        block = (
            f"\nError: {d.error_title}\n"
            f"  Severity: {d.severity}\n"
            f"  Affected repo: {d.affected_repo}\n"
            f"  Root cause: {d.root_cause}\n"
            f"  Suggested fix: {f.suggested_fix}\n"
            f"  Confidence: {f.confidence:.2f}\n"
            f"  Reasoning: {f.reasoning}\n"
        )
        print(block)
        report_lines.append(block)

    if triage_results:
        triage_block = "\n" + "=" * 60 + "\nTRIAGE RANKING\n" + "=" * 60 + "\n"
        print(triage_block)
        report_lines.append(triage_block)
        for t in triage_results:
            line = f"{t.priority_rank}. [{t.action.upper()}] {t.error_title} (Urgency: {t.urgency_score:.2f})"
            print(line)
            report_lines.append(line)

    _HERE = pathlib.Path(__file__).parent
    report_path = _HERE / "report.txt"
    with open(report_path, "w") as out:
        out.write("\n".join(report_lines))

    json_report = {
        "pipeline_version": "2.0",
        "agents": ["RetrieverAgent", "DiagnosisAgent", "FixAgent", "TriageAgent"],
        "diagnoses": [d.__dict__ for d in diagnoses],
        "fixes": [f.__dict__ for f in fixes],
        "triage": [t.__dict__ for t in triage_results]
    }
    json_path = _HERE / "report.json"
    with open(json_path, "w") as out:
        json.dump(json_report, out, indent=2)

    print(f"\nReports saved to {report_path.name} and {json_path.name}")


if __name__ == "__main__":
    run_pipeline()