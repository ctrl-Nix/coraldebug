# CoralDebug Agent

> A multi-agent debugging pipeline across GitHub + Sentry + Slack — powered by Coral SQL

Built for the **Pirates of the Coral-bean Hackathon 2026** by WeMakeDevs × Coral, and recently upgraded to a full production-ready multi-agent architecture.

## What it does

CoralDebug diagnoses production errors by querying GitHub, Sentry, and Slack **using Coral SQL**, and orchestrates an AI pipeline to find the root cause, suggest a fix, and triage the issues by urgency.

Instead of hopping between 3 dashboards, the agent automatically pulls:
- **Sentry** -> unresolved errors in production
- **GitHub** -> affected repositories and languages
- **Slack** -> what the team is saying about it

## Multi-Agent Architecture

Unlike typical single-prompt AI tools, CoralDebug uses a genuine multi-agent handoff system. This prevents context pollution, allows independent testing of stages, and provides structured data at each step.

```text
Architecture
────────────
RetrieverAgent          DiagnosisAgent          FixAgent          TriageAgent
(Coral SQL fetch)  →→→  (root-cause JSON)  →→→  (fix + score) →→→ (priority rank)
     ↑                        ↑                       ↑                  ↑
 sentry.issues          structured Diagnosis    FixSuggestion       TriageResult
 github.repos           dataclass               dataclass           dataclass
 slack.channels
```

### Why Multi-Agent?
A single mega-prompt suffers from attention degradation and makes it impossible to cleanly extract intermediate reasoning. By splitting responsibilities:
1. **RetrieverAgent** handles all external SQL fetching and error boundaries.
2. **DiagnosisAgent** focuses *only* on finding the root cause.
3. **FixAgent** focuses *only* on generating concrete code fixes with confidence scores.
4. **TriageAgent** acts as a cross-agent composer, weighing the severity of the diagnosis against the confidence of the fix to rank issues for engineers.

## Powered by Coral

The RetrieverAgent fetches live telemetry across 3 sources natively:

```sql
SELECT title, level, status, project FROM sentry.issues LIMIT 10
SELECT name, open_issues_count, language FROM github.repositories LIMIT 5
SELECT id, name FROM slack.channels LIMIT 5
```
*(Note: Current pipeline queries Sentry issues, GitHub repos, and Slack channels based on current schema availability).*

## Live Demo

**https://coraldebug.vercel.app/**

## Tech Stack

- **[Coral](https://withcoral.com)** — Cross-source SQL layer
- **Groq (Llama3-70b)** — AI reasoning engine
- **Python** — Multi-agent orchestration
- **Vercel** — Dashboard deployment

## Quick Start

### 1. Install Coral
```bash
# macOS/Linux
brew install withcoral/tap/coral

# Windows
# Download from https://github.com/withcoral/coral/releases
```

### 2. Connect sources
```bash
coral source add github --interactive
coral source add sentry --interactive
coral source add slack --interactive
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
Create a `.env` file in the root directory:
```env
GROQ_API_KEY=your_groq_api_key_here
```

### 5. Run the pipeline
```bash
python agent.py
```
This generates two files:
- `report.txt` — Human-readable ranked triage and fix report.
- `report.json` — Machine-readable structured pipeline output for downstream tools.

### 6. Open the dashboard
Open `index.html` in your browser or visit the live demo.

## Hackathon

Built during **Pirates of the Coral-bean** — May 2026
- Organized by [WeMakeDevs](https://wemakedevs.org)
- Sponsored by [Coral](https://withcoral.com)
