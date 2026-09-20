"""
Gmail Agent
-----------
Fetches unread email, summarizes each message, and drafts a reply for the
ones that actually need one. Drafts are saved into Gmail's own Drafts
folder for you to review and send yourself - this script never sends
anything on its own.

One-time setup:
    1. In Google Cloud Console (console.cloud.google.com), create a
       project (or pick an existing one) and enable the "Gmail API".
    2. Under "APIs & Services > Credentials", create an OAuth Client ID
       of type "Desktop app".
    3. Download the resulting JSON and save it as:
           credentials/client_secret.json
    4. pip install -r requirements.txt
    5. export ANTHROPIC_API_KEY="your-key-here"
    6. python gmail_agent.py
       The first run opens a browser window for you to sign in and grant
       access. After that, a cached token in credentials/token.json is
       reused automatically.

Note on permissions: Gmail doesn't offer a scope that allows creating
drafts but blocks sending, so the OAuth grant below (gmail.compose)
technically permits sending too. This script simply never calls that
endpoint - it only ever calls drafts().create(). You can verify this by
reading the code below.
"""

import os
import sys
import json
import base64
from email.mime.text import MIMEText

# Windows' default console codepage can't print emoji/some Unicode found in
# real email subjects - force UTF-8 stdout so we never crash on printing.
sys.stdout.reconfigure(encoding="utf-8")

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from anthropic import Anthropic

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]

CRED_DIR = os.path.join(os.path.dirname(__file__), "credentials")
CLIENT_SECRET_FILE = os.path.join(CRED_DIR, "client_secret.json")
TOKEN_FILE = os.path.join(CRED_DIR, "token.json")

MODEL = "claude-sonnet-5"
MAX_EMAILS = 10

ANALYSIS_PROMPT = """You are triaging one email for a busy college student. \
Given the email below, respond with ONLY a compact JSON object (no markdown \
fences, no extra text) with exactly these fields:
- "summary": one sentence describing what this email is about
- "needs_reply": true or false - true only if the sender is waiting on a \
response from the student (a question, a request, a scheduling ask). False \
for newsletters, receipts, notifications, automated mail, or FYI-only \
messages.
- "draft_reply": if needs_reply is true, a short, polite, professional \
draft reply in the student's voice, ready to send with minor edits. Empty \
string if needs_reply is false.

Email:
From: {sender}
Subject: {subject}
Body:
{body}
"""


def get_gmail_service():
    """Local/CLI auth: reads credentials/token.json if present, refreshing
    it if expired, or opens a browser for first-time authorization. Only
    works where a local browser is available - not on a cloud deployment.
    """
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CLIENT_SECRET_FILE):
                print(f"ERROR: missing {CLIENT_SECRET_FILE}")
                print("See the setup instructions at the top of this file.")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        os.makedirs(CRED_DIR, exist_ok=True)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def get_gmail_service_from_authorized_token(token_info):
    """Cloud-safe auth: builds a Gmail service from an already-authorized
    token (a dict - the parsed contents of credentials/token.json), and
    refreshes it if expired. Never opens a browser, so this is what
    dashboard.py uses when deployed. Raises if the token has no valid
    refresh token - in that case it needs re-authorizing locally and the
    resulting token.json re-uploaded to the deployment's secrets.
    """
    creds = Credentials.from_authorized_user_info(token_info, SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise RuntimeError(
                "Stored Gmail token is invalid and has no refresh token - "
                "re-authorize locally (delete credentials/token.json and "
                "run gmail_agent.py once) then update the GMAIL_TOKEN secret."
            )
    return build("gmail", "v1", credentials=creds)


def get_anthropic_client():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: Set the ANTHROPIC_API_KEY environment variable before running.")
        sys.exit(1)
    return Anthropic(api_key=api_key)


def fetch_unread_messages(service, max_results=MAX_EMAILS):
    resp = service.users().messages().list(
        userId="me", labelIds=["INBOX", "UNREAD"], maxResults=max_results
    ).execute()
    return resp.get("messages", [])


def extract_body(payload):
    if payload.get("mimeType") == "text/plain" and "data" in payload.get("body", {}):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
    for part in payload.get("parts", []) or []:
        text = extract_body(part)
        if text:
            return text
    if "data" in payload.get("body", {}):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
    return ""


def get_message_detail(service, msg_id):
    msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
    headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
    body = extract_body(msg["payload"])
    return {
        "id": msg_id,
        "thread_id": msg["threadId"],
        "message_id_header": headers.get("Message-ID", ""),
        "from": headers.get("From", "(unknown)"),
        "subject": headers.get("Subject", "(no subject)"),
        "date": headers.get("Date", ""),
        "body": body[:4000],
    }


def analyze_email(client, email):
    prompt = ANALYSIS_PROMPT.format(sender=email["from"], subject=email["subject"], body=email["body"])
    response = client.messages.create(
        model=MODEL,
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in response.content if b.type == "text")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"summary": text.strip()[:200], "needs_reply": False, "draft_reply": ""}


def create_draft_reply(service, email, reply_text):
    message = MIMEText(reply_text)
    message["To"] = email["from"]
    message["Subject"] = "Re: " + email["subject"]
    if email["message_id_header"]:
        message["In-Reply-To"] = email["message_id_header"]
        message["References"] = email["message_id_header"]
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    body = {"message": {"raw": raw, "threadId": email["thread_id"]}}
    service.users().drafts().create(userId="me", body=body).execute()


def check_unread_email(gmail=None, claude=None):
    """Fetch unread mail, summarize each message, and draft replies where
    needed (saved to Gmail Drafts, never sent). Returns a list of dicts:
    {from, subject, summary, draft_created}. Used by both the CLI (main())
    and dashboard.py.

    gmail/claude can be pre-built clients - dashboard.py passes in
    cloud-safe ones (get_gmail_service_from_authorized_token(), a client
    built from st.secrets) when deployed. Left as None, this builds the
    local/CLI versions itself.
    """
    gmail = gmail or get_gmail_service()
    claude = claude or get_anthropic_client()

    messages = fetch_unread_messages(gmail)
    results = []
    for m in messages:
        email = get_message_detail(gmail, m["id"])
        analysis = analyze_email(claude, email)

        draft_created = False
        if analysis.get("needs_reply") and analysis.get("draft_reply"):
            create_draft_reply(gmail, email, analysis["draft_reply"])
            draft_created = True

        results.append({
            "from": email["from"],
            "subject": email["subject"],
            "summary": analysis.get("summary", "(no summary)"),
            "draft_created": draft_created,
        })
    return results


def main():
    results = check_unread_email()
    if not results:
        print("No unread messages.")
        return

    print(f"Found {len(results)} unread message(s).\n")
    for r in results:
        print(f"From: {r['from']}")
        print(f"Subject: {r['subject']}")
        print(f"Summary: {r['summary']}")
        if r["draft_created"]:
            print("-> Draft reply created in Gmail (review before sending).")
        else:
            print("-> No reply needed.")
        print()


if __name__ == "__main__":
    main()
