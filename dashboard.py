"""
Morning Dashboard
-----------------
A local chat dashboard for the morning-brief toolkit. Shows today's
schedule at a glance and lets you ask for email/news updates - or anything
else about your schedule - in a chat, instead of running each script by
hand in a terminal.

Same tool-calling pattern as agent.py, just with a UI and real tools tied
to your own schedule/email/news data instead of a calculator/clock/file
reader.

Run:
    streamlit run dashboard.py
(or double-click start_dashboard.bat)
"""

import json
import os
from datetime import datetime

import streamlit as st
from anthropic import Anthropic

import brief_data
from gmail_agent import check_unread_email, get_gmail_service, get_gmail_service_from_authorized_token
from news_agent import get_curated_news

MODEL = "claude-sonnet-5"
MAX_TOKENS = 1500

SYSTEM_PROMPT = (
    "You are Kshitiz's personal morning assistant. You have tools to check "
    "his class schedule, unread email, and curated science/tech news - use "
    "them whenever they'd help answer his question, rather than guessing. "
    "Keep answers concise and conversational, not a wall of text. "
    "IMPORTANT: never write, draft, or generate content for his coursework "
    "(assignments, discussion posts, quiz or exam answers, papers) - his "
    "Biology course treats that as academic dishonesty. You may track "
    "dates/deadlines and summarize or draft *email* replies only."
)

TOOLS = [
    {
        "name": "get_today_schedule",
        "description": "Get today's classes and anything due today across all of Kshitiz's courses.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_week_ahead",
        "description": "Get upcoming exams, deadlines, and holidays for the next 7 days.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "check_email",
        "description": "Check unread Gmail, summarize each message, and draft replies for the ones that need one (saved to Gmail Drafts - never sent automatically).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_tech_news",
        "description": "Get today's curated science and technology news headlines from RSS feeds.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_project_status",
        "description": "Get the checklist status for multi-part projects (e.g. the Strategic Planning Project) - which requirements are done and which aren't.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


def get_secret(key):
    """st.secrets, but safe to call even when no secrets.toml/Secrets are
    configured at all (local runs without cloud setup)."""
    try:
        return st.secrets.get(key)
    except Exception:
        return None


@st.cache_resource
def get_gmail_service_cloud_aware():
    """Uses the GMAIL_TOKEN secret (deployed) if configured, otherwise
    falls back to the normal local browser-based flow (this laptop)."""
    token_json = get_secret("GMAIL_TOKEN")
    if token_json:
        return get_gmail_service_from_authorized_token(json.loads(token_json))
    return get_gmail_service()


def run_tool(name, client):
    if name == "get_today_schedule":
        return brief_data.get_today_brief()

    if name == "get_week_ahead":
        return brief_data.get_week_ahead_brief()

    if name == "check_email":
        gmail = get_gmail_service_cloud_aware()
        results = check_unread_email(gmail=gmail, claude=client)
        if not results:
            return "No unread messages."
        lines = []
        for r in results:
            lines.append(f"From: {r['from']}\nSubject: {r['subject']}\nSummary: {r['summary']}")
            lines.append("-> Draft reply created in Gmail." if r["draft_created"] else "-> No reply needed.")
        return "\n".join(lines)

    if name == "get_tech_news":
        picks = get_curated_news(client=client)
        if not picks:
            return "No news picks available right now (feeds may be unreachable)."
        lines = []
        for p in picks:
            lines.append(f"{p.get('title')} ({p.get('source')}): {p.get('why_it_matters')} [{p.get('url')}]")
        return "\n".join(lines)

    if name == "get_project_status":
        return brief_data.get_projects_brief()

    return f"Unknown tool: {name}"


@st.cache_resource
def get_client():
    api_key = get_secret("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        st.error(
            "No Anthropic API key found. Locally: set ANTHROPIC_API_KEY in "
            "the environment this app was launched from (setx, or the "
            "terminal you ran `streamlit run` from) and restart. On the "
            "deployment: add it as a Secret named ANTHROPIC_API_KEY."
        )
        st.stop()
    return Anthropic(api_key=api_key)


def check_password():
    """Only enforced when APP_PASSWORD is configured as a secret (the
    public deployment) - local runs without that secret skip the gate."""
    configured = get_secret("APP_PASSWORD")
    if not configured:
        return True
    if st.session_state.get("authenticated"):
        return True
    st.title(":sunny: Morning Brief")
    pw = st.text_input("Password", type="password")
    if pw:
        if pw == configured:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Wrong password.")
    return False


def run_turn(client, history):
    """Runs one full turn: calls the model, executes any requested tools,
    and loops until the model gives a final text answer. Same loop shape
    as agent.py's run_agent_turn.
    """
    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=history,
        )
        history.append({"role": "assistant", "content": response.content})

        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            return "".join(b.text for b in response.content if b.type == "text")

        tool_results = []
        for block in tool_uses:
            with st.spinner(f"Checking {block.name.replace('_', ' ')}..."):
                result = run_tool(block.name, client)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": str(result),
            })
        history.append({"role": "user", "content": tool_results})


def render_history():
    for msg in st.session_state.history:
        role = msg["role"]
        content = msg["content"]
        if role == "user" and isinstance(content, str):
            with st.chat_message("user"):
                st.write(content)
        elif role == "assistant":
            text = "".join(b.text for b in content if getattr(b, "type", None) == "text")
            if text:
                with st.chat_message("assistant"):
                    st.write(text)
        # tool_result user messages (list content) are intentionally not shown


st.set_page_config(page_title="Morning Brief", page_icon=":sunny:", layout="centered")

if not check_password():
    st.stop()

st.title(":sunny: Morning Brief")
st.caption(datetime.now().strftime("%A, %B %d, %Y"))

with st.expander("Today at a glance", expanded=True):
    st.text(brief_data.get_today_brief())

projects_data = brief_data.load_projects()
if projects_data["projects"]:
    with st.expander("Projects", expanded=False):
        for project in projects_data["projects"]:
            done_count = sum(1 for i in project["items"] if i["done"])
            total_count = len(project["items"])
            st.markdown(f"**{project['name']}** ({project['course']}) - due {project['due']} - {done_count}/{total_count} done")
            for item in project["items"]:
                key = f"{project['id']}__{item['id']}"
                checked = st.checkbox(item["label"], value=item["done"], key=key)
                if checked != item["done"]:
                    brief_data.toggle_project_item(project["id"], item["id"])
                    st.rerun()
            st.divider()

if "history" not in st.session_state:
    st.session_state.history = []

render_history()

if prompt := st.chat_input("Ask about your schedule, email, or news..."):
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    client = get_client()
    with st.chat_message("assistant"):
        reply = run_turn(client, st.session_state.history)
        st.write(reply)
