"""
Phase 4: AI Agent with Tools
-----------------------------
Extends the Phase 1 chatbot with tool-calling: the model can now decide
to use tools (functions you define) rather than just generate text.
This is the core mechanic behind every "AI agent" you've seen -
Claude Code, ChatGPT plugins, AutoGPT, etc. all boil down to this loop:

    1. Send the user's message + list of available tools to the model
    2. Model replies with either:
         a) a text answer, OR
         b) a request to call one or more tools
    3. If (b): you run the tool code yourself, send the result back
    4. Repeat until the model gives a final text answer

Setup: same as chatbot.py
    pip install -r requirements.txt
    export ANTHROPIC_API_KEY="your-key-here"
    python agent.py
"""

import os
import sys
import json
from datetime import datetime
from anthropic import Anthropic

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1024
SYSTEM_PROMPT = (
    "You are a helpful assistant with access to tools. "
    "Use them whenever they would give a more accurate or useful answer "
    "than answering from memory alone."
)

# ---------------------------------------------------------------------
# STEP 1: Define your tools
# ---------------------------------------------------------------------
# Each tool needs:
#   - a schema (so the model knows it exists and what arguments it takes)
#   - a real Python function that does the work

def calculator(expression: str) -> str:
    """Safely evaluate a basic arithmetic expression."""
    try:
        # Only allow digits, operators, parentheses, decimal points, spaces
        allowed = set("0123456789+-*/(). ")
        if not set(expression) <= allowed:
            return "Error: expression contains disallowed characters."
        return str(eval(expression, {"__builtins__": {}}))
    except Exception as e:
        return f"Error: {e}"


def get_current_time() -> str:
    """Return the current date and time."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def read_local_file(filename: str) -> str:
    """Read a text file from the local 'agent_files' folder (sandboxed)."""
    safe_dir = os.path.join(os.path.dirname(__file__), "agent_files")
    os.makedirs(safe_dir, exist_ok=True)
    path = os.path.join(safe_dir, os.path.basename(filename))  # prevent path traversal
    if not os.path.exists(path):
        return f"Error: {filename} not found in agent_files/"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()[:5000]  # cap size sent back to the model


# Map tool name -> Python function, so we can call it dynamically later
TOOL_FUNCTIONS = {
    "calculator": lambda args: calculator(args["expression"]),
    "get_current_time": lambda args: get_current_time(),
    "read_local_file": lambda args: read_local_file(args["filename"]),
}

# Schemas describing each tool to the model (Anthropic tool-use format)
TOOLS = [
    {
        "name": "calculator",
        "description": "Evaluate a basic arithmetic expression (+, -, *, /, parentheses).",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "The arithmetic expression to evaluate, e.g. '12 * (3 + 4)'",
                }
            },
            "required": ["expression"],
        },
    },
    {
        "name": "get_current_time",
        "description": "Get the current date and time.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "read_local_file",
        "description": "Read the contents of a text file from the agent's local agent_files/ folder.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Name of the file to read, e.g. 'notes.txt'",
                }
            },
            "required": ["filename"],
        },
    },
]


def get_client() -> Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: Set the ANTHROPIC_API_KEY environment variable before running.")
        sys.exit(1)
    return Anthropic(api_key=api_key)


def run_agent_turn(client: Anthropic, history: list) -> str:
    """
    Runs one full turn: keeps calling the model and executing tools
    until the model returns a final text answer (no more tool calls).
    """
    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=history,
        )

        # Did the model ask to use any tools?
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

        if not tool_use_blocks:
            # No tool calls -> this is the final answer
            final_text = "".join(
                b.text for b in response.content if b.type == "text"
            )
            history.append({"role": "assistant", "content": response.content})
            return final_text

        # The model wants to use one or more tools.
        # Add its request to history, then run each tool and send results back.
        history.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in tool_use_blocks:
            print(f"  [agent is using tool: {block.name}({json.dumps(block.input)})]")
            func = TOOL_FUNCTIONS.get(block.name)
            result = func(block.input) if func else f"Error: unknown tool {block.name}"
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": str(result),
            })

        history.append({"role": "user", "content": tool_results})
        # Loop back around: send the tool results to the model for its next move


def agent_loop() -> None:
    client = get_client()
    history = []

    print("Agent ready (tools: calculator, get_current_time, read_local_file).")
    print("Type 'quit' or 'exit' to stop.\n")

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("quit", "exit"):
            print("Goodbye!")
            break
        if not user_input:
            continue

        history.append({"role": "user", "content": user_input})

        try:
            reply = run_agent_turn(client, history)
        except Exception as e:
            print(f"[Error: {e}]\n")
            history.pop()
            continue

        print(f"Bot: {reply}\n")


if __name__ == "__main__":
    agent_loop()
