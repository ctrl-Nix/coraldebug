"""
review_cli.py

Usage:
    python review_cli.py --diff path/to/changes.diff
    git diff | python review_cli.py --stdin
    python review_cli.py --diff path/to/changes.diff --json   (for the TS CLI to consume)
"""

import argparse
import json
import sys
from orchestrator import ReviewOrchestrator


def main():
    parser = argparse.ArgumentParser(description="SwarmReview: multi-agent code review")
    parser.add_argument("--diff", help="Path to a .diff/.patch file")
    parser.add_argument("--stdin", action="store_true", help="Read diff from stdin")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--api-key", help="Optional Groq API key (overrides .env)")
    args = parser.parse_args()

    if args.stdin:
        diff_text = sys.stdin.read()
    elif args.diff:
        with open(args.diff, "r") as f:
            diff_text = f.read()
    else:
        parser.error("Provide --diff <file> or --stdin")
        return

    orchestrator = ReviewOrchestrator(api_key=args.api_key)
    result = orchestrator.run(diff_text)

    if args.json:
        print(json.dumps({
            "final_verdict": result.final_verdict,
            "final_confidence": result.final_confidence,
            "overruled": result.overruled,
            "specialists": [
                {
                    "agent": v.agent_name,
                    "verdict": v.verdict,
                    "confidence": v.confidence,
                    "reasoning": v.reasoning,
                }
                for v in result.specialist_verdicts
            ],
            "skeptic": {
                "verdict": result.skeptic_verdict.verdict,
                "confidence": result.skeptic_verdict.confidence,
                "reasoning": result.skeptic_verdict.reasoning,
            },
        }, indent=2))
    else:
        print(result.summary)


if __name__ == "__main__":
    main()
