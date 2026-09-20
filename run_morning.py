"""
Morning Routine
---------------
Runs all three morning-brief pieces in sequence: today's class schedule,
unread email summaries/drafts, and curated science/tech news.

Usage:
    python run_morning.py

Each piece is a separate script (see CLAUDE.md for why) - this just calls
them one after another as subprocesses, so a failure in one (e.g. a missing
ANTHROPIC_API_KEY) doesn't stop the others from running.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(__file__)

SCRIPTS = [
    ("Class Schedule", "morning_brief.py"),
    ("Email Summary", "gmail_agent.py"),
    ("Science & Tech News", "news_agent.py"),
]


def run(label, script):
    print("=" * 70)
    print(f"  {label}  ({script})")
    print("=" * 70)
    result = subprocess.run([sys.executable, os.path.join(HERE, script)])
    print()
    return result.returncode == 0


def main():
    results = [(label, run(label, script)) for label, script in SCRIPTS]

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for label, ok in results:
        print(f"  {'OK    ' if ok else 'FAILED'} - {label}")


if __name__ == "__main__":
    main()
