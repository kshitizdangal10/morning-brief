# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Phase 4 (Agents), edging into Phase 5 (Deployment), of an AI Engineering learning progression: **Python → ML → Deep Learning → LLMs/GenAI → RAG → Agents → Deployment**. Started as a minimal tool-calling agent ([agent.py](agent.py)) and has grown into a personal "morning brief" toolkit for the student who owns it (Kshitiz): class schedule tracking, Gmail summarization/reply-drafting, science/tech news curation, and now a Streamlit chat UI ([dashboard.py](dashboard.py)) tying the three together so he doesn't have to run scripts by hand. The README documents an earlier `chatbot.py` (Phase 1, plain conversation, no tools) that does not exist in this directory — don't assume it's present.

## Hard constraint: no AI-authored coursework

The student's Biology 1001 course explicitly bans using AI to generate, edit, paraphrase, or construct assignments, discussion posts, quizzes, or exam answers (treated as academic dishonesty). Treat this as a blanket rule for this repo: tools here may track deadlines and summarize/draft *email*, but must never draft or write content for the student's coursework (assignments, discussion posts, quiz/exam answers, papers).

## Commands

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="your-key-here"

python agent.py             # Phase 4 tool-calling demo agent
python morning_brief.py                    # today's classes + week-ahead deadlines, using today's date
python morning_brief.py --date 2026-09-20  # simulate a specific date (for demos/testing)
python gmail_agent.py       # summarize unread email, draft replies (see setup below)
python news_agent.py        # curated science/tech headlines, picked and summarized by Claude
python run_morning.py       # runs the three CLI scripts above in sequence (subprocess-based)
python -m streamlit run dashboard.py   # chat UI over all three (or double-click start_dashboard.bat)
python daily_alert.py       # Windows toast notification if an exam/deadline is within 3 days (no-op otherwise)
```

`gmail_agent.py` needs one-time Gmail OAuth setup (Google Cloud project with Gmail API enabled, OAuth Client ID of type "Desktop app", saved as `credentials/client_secret.json`) — full steps are in the docstring at the top of that file. `credentials/` is gitignored.

`morning_brief.py` stays fast and offline on purpose — it only reads local `schedule/*.json`, no network or API key needed. `gmail_agent.py` and `news_agent.py` remain separate, independently runnable CLI scripts (need `ANTHROPIC_API_KEY` and network access) — `dashboard.py` imports their reusable functions (`check_unread_email()`, `get_curated_news()`) rather than duplicating logic, but each script's own `main()` still works standalone. Keep that pattern (shared function + thin CLI wrapper) when adding new capabilities.

On this Windows machine, `pip`/`streamlit`/other installed console scripts are not on the shell's `PATH` — always invoke them as `python -m <tool>` (e.g. `python -m pip install ...`, `python -m streamlit run ...`), not bare `pip ...` / `streamlit ...`, or the command silently fails with "command not found".

There is no build, lint, or test tooling in this repo.

## Architecture

### agent.py — tool-calling loop

Implements the tool-calling agent loop that underlies "AI agent" systems generally (Claude Code, ChatGPT plugins, etc.):

1. Send the full conversation `history` plus the `TOOLS` schema list to the model.
2. If the response contains `tool_use` blocks, run the corresponding Python function from `TOOL_FUNCTIONS` for each, append the tool call and its results to `history` as new messages, and loop back to step 1.
3. If the response has no tool calls, it's the final answer — return it.

Key structural points:

- **Tools are defined twice, kept in sync manually**: a JSON schema in `TOOLS` (tells the model what exists and its arguments) and an entry in `TOOL_FUNCTIONS` (name → lambda that calls the real Python function). Adding a tool means updating both.
- **`history` is the only state.** It accumulates every user/assistant/tool-result turn and is resent in full on every API call — the model itself is stateless between calls. History lives only in memory and is lost on exit.
- **`run_agent_turn`** drives the inner loop (model ↔ tools) until a final text answer is produced; **`agent_loop`** drives the outer REPL (reading user input, calling `run_agent_turn`, printing the reply).
- `read_local_file` sandboxes reads to an `agent_files/` folder via `os.path.basename` to prevent path traversal — preserve this pattern if adding similar file-access tools.

### brief_data.py — shared schedule helpers

Pure data functions (JSON loading, date filtering, event formatting) extracted from `morning_brief.py` so `dashboard.py` can reuse the exact same schedule logic instead of duplicating it. `get_today_brief()` / `get_week_ahead_brief()` return plain-text strings (not printed) — `morning_brief.py` imports the lower-level loaders (`load_weekly_schedule`, `events_on`, etc.) directly for its own CLI-specific formatting, while `dashboard.py` calls the two high-level string functions straight. If schedule logic needs to change, change it here once.

### schedule/ — class schedule data

One JSON file per course (`risk_management_insurance.json`, `cins3041_advanced_networking.json`, `cins4030_information_systems_analysis.json`, `mgmt4009_strategic_management.json`, `biology1001_living_world.json`), each with a flat `events` list: `{date, day, type, topic, ...}` where `type` is one of `class`/`exam`/`holiday`/`event`/`deadline`. Optional fields per event: `deadline` (text describing something due, often on a different actual due-date than the class day it's attached to — e.g. a SmartBook reading assigned in Tuesday's class but due Wednesday), `notes`, `time`.

`weekly_schedule.json` is the index: which courses meet which weekdays/times/rooms and which `schedule_file` holds their events. The four business-college courses meet Tue/Thu in person; Biology 1001 is fully online/asynchronous (`days: null`, no fixed meeting time) with weekly Friday deadlines and fixed-date exams instead.

This data was transcribed from the student's actual syllabi (PDF/DOCX) — when adding a new course, follow the same shape so `morning_brief.py` picks it up automatically without code changes.

`schedule/projects.json` tracks multi-part projects separately (currently the MGMT 4009 Strategic Planning Project, with a real checklist of requirements transcribed from the syllabus's Appendix A — formatting rules, report sections, submission steps; Biology's Build-A-Beast Project is a stub since its actual instructions were never captured from the syllabus). Checklist items are booleans toggled from `dashboard.py`'s UI via `brief_data.toggle_project_item()`, which writes straight back to this file — it's the one piece of schedule state that isn't read-only. **Important distinction for checklist items:** they track compliance with stated requirements (page count, formatting, "is it Word not PDF," "did you cite properly") — never the content of the work itself (don't add an item like "write the SWOT analysis" with AI-generated suggestions). That line is what keeps this feature inside the no-AI-coursework rule above.

The 34 highest-stakes entries (all exams, major project/paper deadlines, mandatory discussion posts, attendance-required events — deliberately excluding routine weekly SmartBook/reading checkpoints to avoid calendar clutter) are also synced as all-day Google Calendar events with a 1-day-before popup reminder, on the student's personal Google Calendar. This was a one-time manual sync via calendar MCP tools, not a script — if the schedule data changes (a syllabus gets revised) or a new course is added, the calendar copy will drift and needs to be manually reconciled; there's no automated sync keeping them in lockstep.

### morning_brief.py — daily digest

Reads `schedule/weekly_schedule.json` plus each course's event file and prints: today's classes/deadlines (including online-only courses, matched by having no `days`), a 7-day lookahead filtered to exam/deadline/holiday/event-type entries (plus any `class`-type entry that happens to carry a `deadline`), and a pointer to run `gmail_agent.py` / `news_agent.py` separately for email and news. `--date` overrides "today" for testing/demos without waiting for real dates.

### gmail_agent.py — email summarizer + reply drafter

Standalone script, independent of any interactive Claude session — reads unread Gmail via the Gmail API (OAuth, token cached in `credentials/token.json`), and for each message calls the Anthropic API (same pattern as `agent.py`) to get a one-line summary plus a needs-reply judgment and draft text. When a reply is warranted, it creates a Gmail **draft** via `drafts().create()` — it never calls a send endpoint. Note: the `gmail.compose` OAuth scope technically permits sending too (Gmail has no draft-only scope), so the safety boundary here is enforced by what the code calls, not by the grant itself — don't add a call to `drafts().send()` or `messages().send()` without the student explicitly asking for auto-send, which changes the safety posture of this tool significantly.

### news_agent.py — science/tech news curator

Standalone script. Pulls the latest entries (`ENTRIES_PER_FEED`, currently 4) from each RSS feed in the `FEEDS` list (Ars Technica, MIT Technology Review, Nature News, Wired, Hacker News front page via hnrss.org) using `feedparser`, pools them, then makes **one** Anthropic API call asking Claude to select and summarize the `TOP_N` (currently 6) most significant stories — not a per-item call like `gmail_agent.py`, since ranking/picking across the whole pool needs to see everything at once. Returns/parses a JSON array (`title`, `source`, `url`, `why_it_matters`). Edit `FEEDS` to add/remove sources; each feed is fetched independently and a parse failure on one is logged and skipped rather than crashing the run.

Both `gmail_agent.py` and `news_agent.py` call `sys.stdout.reconfigure(encoding="utf-8")` at startup — real email subjects and headlines often contain emoji/non-ASCII characters that crash on Windows' default console codepage otherwise. Keep this in any new script that prints fetched external content. Both also expose their core logic as a plain function (`check_unread_email()`, `get_curated_news()`) that returns structured data, with `main()` as a thin CLI wrapper around it — `dashboard.py` imports and calls these functions directly rather than shelling out.

### run_morning.py — sequential CLI runner

Thin orchestrator: runs `morning_brief.py`, `gmail_agent.py`, `news_agent.py` in sequence via `subprocess.run`, printing a pass/fail summary at the end. Uses subprocesses (not imports) deliberately, so one script's `sys.exit()` (e.g. `gmail_agent.py` exiting when `ANTHROPIC_API_KEY` is unset) can't kill the others. Superseded for everyday use by `dashboard.py`, but still useful as a plain-terminal fallback.

### dashboard.py — chat UI (Streamlit)

The "talk with this and get updates" interface the student asked for instead of running scripts by hand. A Streamlit app that: (1) renders today's schedule inline via `brief_data.get_today_brief()` on load — instant, no API call; (2) runs a tool-calling chat loop structurally identical to `agent.py`'s (`run_turn` here == `run_agent_turn` there), except the tools are `get_today_schedule`, `get_week_ahead`, `check_email`, `get_tech_news` — the last two call straight into `gmail_agent.check_unread_email()` / `news_agent.get_curated_news()`. Chat history lives in `st.session_state.history` and is the same message-list shape the Anthropic API expects (raw `response.content` is appended for assistant turns, so tool_use/tool_result blocks round-trip correctly) — `render_history()` re-derives the display from that same list on every rerun rather than keeping a separate display-only transcript, so don't let the two diverge.

Launch with `python -m streamlit run dashboard.py` or by double-clicking `start_dashboard.bat` (which does the same, `cd`'d into this folder first). Needs `ANTHROPIC_API_KEY` set in the environment the process starts from — on this machine that's `setx`'d permanently, so any freshly-opened terminal or Explorer-launched process should already have it. **UI quirk:** the chat input's Enter key does not submit — Streamlit's `st.chat_input` requires clicking the send arrow; don't "fix" this by trying to intercept Enter, it's a Streamlit component behavior, not a bug in this code.

"Sidebar dock" in the request meant a persistent side-of-screen panel, not literal Windows OS sidebar/Widgets integration (not realistically pluggable for a personal script) — the practical equivalent shipped here is a local browser tab the student snaps to the side of the screen (Win+Right arrow), installed as a standalone Edge app (Edge's "Install this site as an app") so it gets its own taskbar icon/name instead of showing a raw `localhost:8501` URL.

### daily_alert.py — proactive Windows notification

The one piece of this toolkit that reaches the student without him opening anything. Reuses `brief_data`'s loaders directly (not the CLI-formatted `get_*_brief()` strings) to find exam/deadline-type entries in the next `LOOKAHEAD_DAYS` (3), then fires a Windows toast via `win11toast` — silently does nothing if there's nothing urgent, so it won't train him to ignore it. Deliberately a separate script from `dashboard.py` rather than something the dashboard triggers on load, because it needs to fire on a fixed clock time (e.g. 7:30 AM) whether or not he's logged in and the dashboard happens to be open that day.

### Windows persistence setup (Startup folder + Task Scheduler)

Two separate auto-run mechanisms are registered on this machine, both outside this repo (so a fresh clone/machine won't have them — they're host setup, not project files):

- **`start_dashboard_hidden.vbs`** (in this repo) is launched via a shortcut in `shell:startup` (`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\MorningBriefDashboard.lnk`) — fires at every Windows logon, no admin rights needed. This is what makes the dashboard "just there" when the student logs in.
- **`daily_alert.py`** is launched via a genuine Task Scheduler task (`MorningBriefDailyAlert`) with a daily time trigger — Startup-folder items only fire at logon, not at a fixed clock time, so a real scheduled task was unavoidable here.

**Important tooling note for future sessions:** this agent cannot register Windows Task Scheduler tasks directly — `Register-ScheduledTask` gets blocked by an "Unauthorized Persistence" auto-mode classifier, and even when the student runs it themselves, it additionally requires an **elevated (Run as Administrator) PowerShell window**, or it fails with "Access is denied" even for a task that itself runs at normal privileges. When a new auto-run capability is needed: prepare the exact script/command, then hand the registration command to the student to run themselves — don't attempt to route around the block via a different tool. The Startup-folder trick (`WScript.Shell.CreateShortcut`) is the one auto-run mechanism that doesn't need admin and isn't blocked, but only supports "at logon," not a specific time.

### Not yet done: public deployment

The student's own README roadmap names this as the next phase ("wrap this in a Streamlit... web UI... and host it"). Not started as of this session — it involves creating an account on an external host (Render/Railway/etc.), likely real cost, and non-trivial security work before it's safe to expose (this app currently has Gmail draft-write access and reads personal schedule/email data; an unauthenticated public deployment would hand that to anyone with the URL, and the Gmail OAuth redirect URI would need updating for a public domain too). Treat this as a separate scoped conversation with the student, not something to start unilaterally.
