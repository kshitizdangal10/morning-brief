"""
News Agent
----------
Pulls recent headlines from a curated list of science/tech RSS feeds, then
asks Claude to pick out and summarize the handful that are actually worth
knowing about - not just dump every headline.

Setup: same as gmail_agent.py
    pip install -r requirements.txt
    export ANTHROPIC_API_KEY="your-key-here"
    python news_agent.py

Edit the FEEDS list below to add/remove sources.
"""

import os
import sys
import re
import json

import feedparser
from anthropic import Anthropic

# Windows' default console codepage can't print some Unicode found in
# real headlines - force UTF-8 stdout so we never crash on printing.
sys.stdout.reconfigure(encoding="utf-8")

FEEDS = [
    {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index"},
    {"name": "MIT Technology Review", "url": "https://www.technologyreview.com/feed/"},
    {"name": "Nature News", "url": "https://www.nature.com/nature.rss"},
    {"name": "Wired", "url": "https://www.wired.com/feed/rss"},
    {"name": "Hacker News (Front Page)", "url": "https://hnrss.org/frontpage"},
]

ENTRIES_PER_FEED = 4
TOP_N = 6
MODEL = "claude-sonnet-5"

CURATE_PROMPT = """You are curating a daily science & technology briefing for a \
busy Computer Information Systems student. Below is a pooled list of recent \
headlines from several reputable outlets. Select the {top_n} most \
significant, genuinely interesting stories - a mix of real developments, not \
clickbait, sponsored content, or pure opinion pieces. Respond with ONLY a \
JSON array (no markdown fences, no extra text), ordered most important \
first, where each item has:
- "title": the headline, lightly tightened for clarity if needed
- "source": the outlet name, copied exactly from the list below
- "url": the article link, copied exactly from the list below
- "why_it_matters": one punchy sentence on why this is worth knowing about

Headlines:
{headlines}
"""


def strip_html(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()


def fetch_headlines():
    items = []
    for feed in FEEDS:
        try:
            parsed = feedparser.parse(feed["url"])
        except Exception as e:
            print(f"  (skipping {feed['name']}: {e})")
            continue
        if parsed.bozo and not parsed.entries:
            print(f"  (skipping {feed['name']}: could not parse feed)")
            continue
        for entry in parsed.entries[:ENTRIES_PER_FEED]:
            items.append({
                "source": feed["name"],
                "title": strip_html(entry.get("title", "")),
                "summary": strip_html(entry.get("summary", ""))[:300],
                "url": entry.get("link", ""),
            })
    return items


def format_headlines_for_prompt(items):
    lines = []
    for i, item in enumerate(items, 1):
        lines.append(
            f"{i}. [{item['source']}] {item['title']}\n"
            f"   Summary: {item['summary']}\n"
            f"   URL: {item['url']}"
        )
    return "\n".join(lines)


def get_anthropic_client():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: Set the ANTHROPIC_API_KEY environment variable before running.")
        sys.exit(1)
    return Anthropic(api_key=api_key)


def curate(client, items):
    prompt = CURATE_PROMPT.format(
        top_n=TOP_N,
        headlines=format_headlines_for_prompt(items),
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in response.content if b.type == "text")
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print("Could not parse Claude's response as JSON - raw output:")
        print(text)
        return []


def get_curated_news(client=None):
    """Fetch headlines from FEEDS and ask Claude to pick/summarize the top
    ones. Returns a list of dicts: {title, source, url, why_it_matters}.
    Used by both the CLI (main()) and dashboard.py.

    client can be a pre-built Anthropic client - dashboard.py passes in
    one built from st.secrets when deployed. Left as None, this builds it
    from the local ANTHROPIC_API_KEY environment variable itself.
    """
    items = fetch_headlines()
    if not items:
        return []
    client = client or get_anthropic_client()
    return curate(client, items)


def main():
    print("Fetching headlines...")
    picks = get_curated_news()

    if not picks:
        print("No headlines fetched, or no stories selected - check your internet connection or the FEEDS list.")
        return

    print(f"Today's top {len(picks)} science & tech stories:\n")
    for i, pick in enumerate(picks, 1):
        print(f"{i}. {pick.get('title', '(no title)')} - {pick.get('source', '?')}")
        print(f"   {pick.get('why_it_matters', '')}")
        print(f"   {pick.get('url', '')}")
        print()


if __name__ == "__main__":
    main()
