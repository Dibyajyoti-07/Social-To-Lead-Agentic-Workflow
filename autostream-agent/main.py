import os
import sys
from dotenv import load_dotenv

# Load env vars (GROQ_API_KEY) before importing agent modules
load_dotenv()

if not os.environ.get("GROQ_API_KEY"):
    print("❌  GROQ_API_KEY not found in environment.")
    print("    Please copy .env.example → .env and add your key.")
    print("    Get a free key at https://console.groq.com\n")
    sys.exit(1)

from agent.graph import compiled_graph
from agent.state import AgentState


def main():
    # Initialise state — persisted across all turns
    state: AgentState = {
        "messages": [],
        "intent": None,
        "lead_name": None,
        "lead_email": None,
        "lead_platform": None,
        "lead_captured": False,
        "awaiting": None,
    }

    print("=" * 60)
    print("  🎬  AutoStream AI Agent  |  Type 'quit' to exit")
    print("=" * 60)
    print()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye! 👋")
            break

        if not user_input:
            continue

        if user_input.lower() in {"quit", "exit", "bye"}:
            print("Agent: Thanks for chatting! Have a great day. 👋\n")
            break

        # Append user turn to history
        state["messages"].append({"role": "user", "content": user_input})

        # Invoke the graph — returns updated state
        state = compiled_graph.invoke(state)

        # Print the last assistant message
        for msg in reversed(state["messages"]):
            if msg["role"] == "assistant":
                print(f"\nAgent: {msg['content']}\n")
                break

        # Stop accepting new input once lead is captured
        if state.get("lead_captured"):
            print("─" * 60)
            print("  Lead captured! Session complete. Type 'quit' to exit.")
            print("─" * 60)


if __name__ == "__main__":
    main()

