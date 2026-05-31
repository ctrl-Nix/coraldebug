import subprocess
import os
from groq import Groq

# ---- CONFIG ----
GROQ_API_KEY = input("🔑 Enter your Groq API key: ")

client = Groq(api_key=GROQ_API_KEY)

def run_coral(query):
    result = subprocess.run(
        ["coral", "sql", query, "--output", "json"],
        capture_output=True, text=True
    )
    return result.stdout

def get_sentry_issues():
    return run_coral("SELECT title, level, status, culprit FROM sentry.issues LIMIT 10")

def get_github_repos():
    return run_coral("SELECT name, open_issues_count, language FROM github.repositories LIMIT 10")

def get_slack_messages():
    return run_coral("SELECT id, name FROM slack.channels LIMIT 5")

def diagnose(sentry, github, slack):
    prompt = f"""
You are an expert debugging agent. Analyze this data and provide:
1. Root cause of each Sentry error
2. Which GitHub repo is likely affected
3. What the team is saying in Slack
4. Recommended fix for each error

SENTRY ERRORS:
{sentry}

GITHUB REPOS:
{github}

SLACK CHANNELS:
{slack}

Give a clear, actionable diagnosis for each error.
"""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500
    )
    return response.choices[0].message.content

def main():
    print("🏴 CoralDebug Agent Starting...")
    print("Querying Sentry for errors...")
    sentry = get_sentry_issues()
    print("Querying GitHub repos...")
    github = get_github_repos()
    print("Querying Slack channels...")
    slack = get_slack_messages()
    print("\n🤖 Analyzing with AI...\n")
    diagnosis = diagnose(sentry, github, slack)
    print("=" * 60)
    print("DIAGNOSIS REPORT")
    print("=" * 60)
    print(diagnosis)
    print("=" * 60)
    with open("report.txt", "w") as f:
        f.write("CORALDEBUG REPORT\n")
        f.write("=" * 60 + "\n")
        f.write("SENTRY DATA:\n" + sentry + "\n")
        f.write("GITHUB DATA:\n" + github + "\n")
        f.write("SLACK DATA:\n" + slack + "\n")
        f.write("AI DIAGNOSIS:\n" + diagnosis + "\n")
    print("\nReport saved to report.txt")

if __name__ == "__main__":
    main()
