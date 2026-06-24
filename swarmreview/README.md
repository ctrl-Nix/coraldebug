# SwarmReview

A local-first, multi-agent code review engine. Instead of one LLM giving one
opinion on a diff, four specialized agents review it independently — and a
fifth **skeptic** agent stress-tests their verdicts before a final decision
is reached.

> Sister project to [CoralDebug](https://github.com/ctrl-Nix/coraldebug) —
> same lane (AI-assisted dev tooling), one level deeper: multi-agent
> orchestration instead of a single LLM call, and local inference by default
> instead of cloud-only.

## Why this exists

Single-LLM code review tools all share the same failure mode: one model,
one pass, one opinion, presented with false confidence. SwarmReview treats
review as a **debate**, not a lookup:

1. Three specialist agents (security, performance, architecture) review the
   diff independently, each blind to the others' opinions.
2. A skeptic agent then reviews *their verdicts*, not the diff directly —
   looking for groupthink, overcautious flags, or weak shared reasoning.
3. The verdicts converge into one final call via confidence-weighted
   resolution (see `orchestrator.py` for the exact rules and the reasoning
   behind them — this is the core design decision of the project).

## Architecture

```
                 ┌─────────────┐
   diff ───────▶ │  Security   │──┐
                 └─────────────┘  │
                 ┌─────────────┐  │      ┌──────────┐      ┌────────────┐
   diff ───────▶ │ Performance │──┼─────▶│ Skeptic  │─────▶│ Orchestrator│──▶ verdict
                 └─────────────┘  │      └──────────┘      └────────────┘
                 ┌─────────────┐  │
   diff ───────▶ │ Architecture│──┘
                 └─────────────┘

   Each agent ──▶ model/llm_client.py ──▶ local Ollama (default)
                                      └──▶ Groq cloud (fallback only)
```

- **`agents/`** — one file per agent persona. Each is a system prompt +
  a structured output contract (verdict / confidence / reasoning), nothing
  more. The skeptic is the only agent that reads peers' outputs, not the diff.
- **`model/llm_client.py`** — the only place that talks to a model. Local
  Ollama by default, Groq fallback if local is unreachable. Agents never
  call a model directly.
- **`orchestrator.py`** — where four opinions become one verdict. Documented
  inline: why confidence-weighted resolution beats plain majority vote, and
  why security blocks act as a veto unless explicitly overruled.
- **`cli/`** — TypeScript CLI shell. Owns UX only (colors, output format);
  all logic lives in Python. Calls the Python engine as a subprocess.

## Setup

```bash
# 1. Local model (required for default path)
ollama pull llama3.1:8b
ollama serve

# 2. Python engine
pip install -r requirements.txt

# 3. (optional) Cloud fallback
export GROQ_API_KEY=your_key_here

# 4. CLI
cd cli && npm install && npm run build
```

## Usage

```bash
# Direct Python engine
git diff > changes.diff
python review_cli.py --diff changes.diff

# Via the TS CLI (after build)
node cli/dist/index.js changes.diff

# Machine-readable output
python review_cli.py --diff changes.diff --json
```

## Running tests

```bash
python -m pytest tests/ -v
```

Tests target the orchestrator's resolution logic directly (no model calls),
so they run in milliseconds and verify the actual decision rules rather than
model output variance — see `tests/test_orchestrator.py`.

## What's intentionally NOT here yet

- Batched/parallel agent calls (agents currently run sequentially — the
  obvious next optimization once correctness is solid)
- A GitHub PR bot wrapper (CLI-first, bot integration is the natural next step)
- Streaming output (waits for full agent responses before printing)

These are left explicit rather than silently absent, because "what you chose
not to build yet and why" is as informative as what's built.

## License

MIT
