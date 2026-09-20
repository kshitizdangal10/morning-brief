# AI Engineering Chatbot Project

Phase 1 of the AI Engineering learning progression:
**Python → ML → Deep Learning → LLMs/GenAI (you are here) → RAG → Agents → Deployment**

## What this is

A minimal, working command-line chatbot that talks to Claude via the Anthropic API
and remembers the conversation within a session. It's intentionally simple —
the point is to have a real, running foundation before adding complexity.

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="your-key-here"
python chatbot.py
```

Get an API key at https://console.anthropic.com/

## How it works

- `history` is a list that accumulates every user/assistant turn
- Each API call sends the *entire* history, so the model has full context
- The model itself has no memory between calls — the app supplies it

## Files

- `chatbot.py` — Phase 1: plain conversational chatbot
- `agent.py` — Phase 4: adds tool-calling. The model can now choose to call
  `calculator`, `get_current_time`, or `read_local_file` instead of just
  generating text. Run it the same way: `python agent.py`

### How the agent loop works

1. Send the conversation + a list of tool schemas to the model
2. Model replies with either final text, or a request to call a tool
3. If it's a tool request: your code runs the real function, sends the
   result back as a new message
4. Repeat until the model has enough information to give a final answer

This request/respond/repeat cycle is the mechanism behind every "AI agent"
you've heard of — Claude Code, ChatGPT plugins, AutoGPT, etc. are all
variations on this same loop, usually with more tools and more guardrails.

## Roadmap (next phases)

1. **Personality/purpose** — customize `SYSTEM_PROMPT` for a specific role
   (study buddy, construction Q&A, etc.)
2. **RAG** — load documents (PDFs, notes), chunk + embed them, store in a
   vector DB (Chroma or FAISS), retrieve relevant chunks and inject them
   into the prompt before calling the model
3. **Agents** ✅ — see `agent.py`. Next step here: add more tools (web
   search, a real database, an email sender) and add safety limits (max
   tool calls per turn, confirmation before destructive actions)
4. **Deployment** — wrap this in a Streamlit or Flask web UI, or a
   Slack/Discord bot, and host it (Render, Railway, a small VPS)

## Notes

- Conversation history currently lives only in memory — it's lost when you
  quit. Persisting it (to a file or database) is a good next small step
  before jumping to RAG.
- Swapping to OpenAI or a local model (Ollama) later mainly means changing
  the client setup and the response-parsing line — the loop structure stays
  the same.
