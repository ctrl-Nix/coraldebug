# 🏴‍☠️ CoralDebug Agent

> AI-powered debugging agent across GitHub + Sentry + Slack — powered by Coral SQL

Built for the **Pirates of the Coral-bean Hackathon 2026** by WeMakeDevs × Coral.

## 🎯 What it does

CoralDebug is an AI agent that diagnoses production errors by querying GitHub, Sentry, and Slack **in a single cross-source SQL query** using Coral. No ETL, no glue code, no context window stuffing.

Instead of hopping between 3 dashboards, you get one unified view:
- 🔴 **Sentry** → unresolved errors in production
- 🐙 **GitHub** → affected repositories and languages
- 💬 **Slack** → what the team is saying about it

Then Groq AI analyzes everything and gives you a root cause diagnosis + recommended fix.

## 🪸 Powered by Coral

The magic is one SQL query across 3 live sources:

```sql
SELECT
  s.title        AS error,
  s.level        AS severity,
  s.status       AS error_status,
  g.name         AS repo,
  g.language     AS lang,
  c.name         AS slack_channel
FROM sentry.issues s
CROSS JOIN github.repositories g
CROSS JOIN slack.channels c
WHERE s.status = 'unresolved'
LIMIT 10
```

Coral handles auth, pagination, rate limits, and schema mapping for all 3 sources. Everything runs 100% locally.

## 🚀 Live Demo

👉 **https://coraldebug.vercel.app/**

## 🛠️ Tech Stack

- **[Coral](https://withcoral.com)** — Cross-source SQL layer
- **Groq (Llama3-70b)** — AI diagnosis engine
- **GitHub API** — Repository and issue data
- **Sentry** — Error tracking
- **Slack** — Team communication
- **Vercel** — Deployment

## ⚡ Quick Start

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
pip install groq sentry-sdk
```

### 4. Add your Groq API key
Edit `agent.py` and replace `YOUR_GROQ_KEY_HERE` with your key from console.groq.com

### 5. Run the agent
```bash
python agent.py
```

### 6. Open the dashboard
Open `index.html` in your browser or visit the live demo.

## 📊 Features

- ✅ Cross-source SQL JOIN across GitHub + Sentry + Slack
- ✅ AI-powered root cause analysis via Groq
- ✅ Beautiful real-time dashboard
- ✅ 100% local — credentials never leave your machine
- ✅ Zero ETL, zero glue code

## 🏴‍☠️ Hackathon

Built during **Pirates of the Coral-bean** — May 2026
- Organized by [WeMakeDevs](https://wemakedevs.org)
- Sponsored by [Coral](https://withcoral.com)
