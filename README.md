# Morning Brief

A personal AI agent that tracks my class schedule, summarizes and drafts replies to my email, and curates science/tech news — surfaced through a chat interface I can talk to, deployed and reachable from any device.

**Live app:** [dangal-morning-brief.streamlit.app](https://dangal-morning-brief.streamlit.app) (password-protected)

Built as the capstone of a self-directed AI Engineering learning progression: `Python → ML → Deep Learning → LLMs/GenAI → RAG → Agents → Deployment`. What started as a minimal tool-calling chatbot (`agent.py`) grew into a small production system: real OAuth integrations, a shared data layer, a deployed web UI, and a few hard calls about what an AI agent should and shouldn't be allowed to do.

## What it does

Every morning I want to know: what's due today, what's coming up this week, what's actually worth reading in my inbox, and what's happening in tech. This project answers all four, either from a terminal or from a chat UI I can open on my phone:

- **Class schedule tracking** — exam dates, project deadlines, and assignment due dates for 5 courses, transcribed from real syllabi (PDF/DOCX) into structured data, with a 7-day lookahead view.
- **Email triage** — reads unread Gmail, summarizes each message, and **drafts** a reply for anything that actually needs one. Drafts land in Gmail's own Drafts folder; nothing is ever sent automatically.
- **Curated tech news** — pulls headlines from a handful of RSS feeds (Ars Technica, MIT Technology Review, Nature, Wired, Hacker News) and asks Claude to pick and summarize the handful actually worth reading, instead of dumping every headline.
- **Project checklists** — tracks multi-part assignments (e.g. a semester-long strategic planning project) as a real checklist of *stated requirements* — formatting rules, submission steps — not the content of the work itself.
- **A chat interface** to ask for any of the above conversationally ("what's due this week?", "check my email"), instead of running scripts by hand.

## Architecture

The core pattern is the same tool-calling loop behind every LLM agent (Claude Code, ChatGPT plugins, etc.), first built as a minimal standalone script and then reused, unchanged in shape, for the deployed chat UI:

```
send (conversation + tool schemas) to the model
  → model replies with text, or a request to call a tool
  → if a tool call: run the real function, send the result back
  → repeat until the model has a final answer
```

`agent.py` is the from-scratch version of this loop (calculator/clock/file-reader tools, for learning). `dashboard.py` is the same loop in production, with tools wired to real systems instead of toys:

| Tool | Backs onto |
|---|---|
| `get_today_schedule` / `get_week_ahead` | Local JSON schedule data (`brief_data.py`) |
| `check_email` | Gmail API (OAuth2), summarized + triaged by Claude |
| `get_tech_news` | RSS feeds, ranked + summarized by Claude in one call |
| `get_project_status` | Per-project checklist state (persisted to disk) |

**Data layer.** Each course's schedule lives in its own JSON file (`schedule/*.json`) with a flat, typed event list (`class` / `exam` / `deadline` / `holiday` / `event`). This is deliberately dumb data, not a database — it's version-controlled, diffable, and trivial to extend with a new course by following the same shape. `brief_data.py` is the one place that knows how to read it, shared by both the CLI digest (`morning_brief.py`) and the web dashboard so the two never drift apart.

**Standalone-first design.** `gmail_agent.py` and `news_agent.py` are fully independent CLI scripts — each has real value on its own (`python gmail_agent.py` just works from a terminal) — but each also exposes its core logic as a plain function (`check_unread_email()`, `get_curated_news()`) that the dashboard imports directly. One codepath, two front ends, instead of the dashboard shelling out to the CLI or duplicating logic.

**Local vs. cloud auth.** The Gmail integration was built for a local script (OAuth via a browser popup on the same machine). Deploying it meant that assumption broke — a cloud server can't pop open a browser. Rather than rebuilding the flow, `gmail_agent.py` grew a second entry point, `get_gmail_service_from_authorized_token()`, that takes an already-authorized token and refreshes it silently; the dashboard tries the cloud path first (a token stored as an encrypted secret) and falls back to the local browser flow if it's not there. Same account, same permissions, two ways to obtain the credential depending on where the code is actually running.

## Engineering decisions worth calling out

- **Email replies are draft-only, on purpose.** Gmail's OAuth scopes don't offer a "draft but never send" permission — the grant technically allows sending. The safety boundary here is enforced by what the code calls (`drafts().create()`, never `drafts().send()` or `messages().send()`), not by the permission grant itself. That's a real constraint, not an oversight, and it's documented as a hard rule for anyone (including an AI assistant) extending this code later.
- **The agent will draft your emails but won't touch your coursework.** One of the five tracked courses explicitly treats AI-generated assignment content as academic dishonesty. Rather than trying to detect that per-request, the system prompt and the project-checklist feature both encode a blanket rule: track dates and requirements, never generate the content of the work itself. A checklist item can say "cite your sources correctly" — it can't say "here's a SWOT analysis draft."
- **News curation is one call, not N calls.** Summarizing each headline individually would be cheaper per-call but worse at the actual job — picking the 6 best stories out of 20 needs to see all 20 at once to compare them, so `news_agent.py` pools every feed first and asks Claude to rank in a single pass.
- **The schedule data intentionally excludes calendar clutter.** Of ~75 transcribed events across 5 courses, only the 34 highest-stakes ones (exams, major deadlines, mandatory attendance) are synced to Google Calendar — routine weekly reading checkpoints are tracked in the app but deliberately left off the calendar, on the theory that a calendar buried in 20 near-identical low-stakes reminders trains you to ignore all of them.

## Stack

Python, the Anthropic API (`claude-sonnet-5`), Streamlit for the UI, the Gmail API (OAuth2), `feedparser` for RSS, deployed on Streamlit Community Cloud from this repo with secrets (API keys, OAuth tokens, app password) held outside the codebase.

## Running it locally

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="your-key-here"

python morning_brief.py       # today's schedule + week ahead (offline, instant)
python gmail_agent.py         # summarize unread email, draft replies (needs Gmail OAuth - see setup below)
python news_agent.py          # curated tech news
python -m streamlit run dashboard.py   # the chat UI, all of the above in one place
```

`gmail_agent.py` needs a one-time Gmail OAuth setup (a Google Cloud project with the Gmail API enabled, and an OAuth Client ID) — full steps are in the docstring at the top of that file.

## What's next

A proper eval set for the news-curation and email-triage prompts, and probably a second, cheaper model tier (Haiku) for the parts of the pipeline that don't need Sonnet-level judgment.
