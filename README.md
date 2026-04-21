# 🎬 AutoStream AI Agent

A conversational AI agent for **AutoStream** — a fictional SaaS for AI-powered video editing tools. The agent:

- 🧠 **Identifies user intent** (greeting, product inquiry, or high-intent to buy)
- 📚 **Answers questions via RAG** from a local ChromaDB knowledge base
- 🎯 **Detects high-intent leads** and captures their details (name, email, platform) via a mock tool

All frameworks, models, and tools are **free and open-source**.

---

## Tech Stack

| Component | Choice |
|---|---|
| Agent Framework | LangGraph (stateful multi-turn) |
| LLM | Groq free tier — Llama 3.1 8B (`llama-3.1-8b-instant`) |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (local) |
| Vector Store | ChromaDB (local, persistent) |
| RAG | LangChain + ChromaDB + sentence-transformers |
| UI | CLI |

---

## How to Run

```bash
# 1. Clone and enter the project
git clone <repo>
cd autostream-agent

# 2. Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\activate      # Windows
# source venv/bin/activate   # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure your API key
cp .env.example .env
# Open .env and paste your GROQ_API_KEY
# Get one free at https://console.groq.com (no credit card required)

# 5. Run the agent
python main.py
```

---

## Architecture (~200 words)

**LangGraph** was chosen because it provides explicit, typed state management via a `TypedDict` state dict. Every turn, the same state object flows into `graph.invoke()`, making multi-turn memory trivial — fields like `lead_name` and `awaiting` persist naturally without a database.

The **RAG pipeline** uses `sentence-transformers/all-MiniLM-L6-v2` to embed the `autostream_kb.md` knowledge base locally. Chunks are stored in **ChromaDB** (persisted to disk under `chroma_db/`). On each product-inquiry turn, the top-2 most relevant chunks are retrieved via cosine similarity and injected directly into the LLM's system prompt — grounding all pricing and policy answers in verified content, preventing hallucination.

**Intent classification** is a separate lightweight LLM call with a constrained, label-only output prompt. Running it fresh on every turn means intent shifts mid-conversation (e.g., from inquiry to high-intent) are caught immediately.

**Tool execution** (`mock_lead_capture`) is gated by a conditional edge — the `lead_capture` node only fires when *all three* fields (name, email, platform) are non-None. Until then, `lead_collection_node` loops back, asking for the next missing field one at a time.

---

## WhatsApp Deployment via Webhooks

To deploy this agent on WhatsApp:

1. **Wrap the agent in FastAPI** — expose a `POST /webhook` endpoint that accepts the WhatsApp message payload.
2. **Extract user text and phone number** from the incoming webhook body.
3. **Session management** — use the phone number as a session key. Store per-user `AgentState` in an in-memory dict (or Redis for production persistence).
4. **Invoke the graph** — call `compiled_graph.invoke(state)` with the user's current state.
5. **Reply** — send the last assistant message back via the WhatsApp Business API (Meta Cloud API or Twilio WhatsApp sandbox).

```python
# Sketch — FastAPI webhook endpoint
from fastapi import FastAPI, Request
from agent.graph import compiled_graph

app = FastAPI()
sessions = {}  # phone_number → AgentState

@app.post("/webhook")
async def webhook(request: Request):
    body = await request.json()
    phone = body["from"]
    text = body["text"]["body"]

    state = sessions.get(phone, {
        "messages": [], "intent": None,
        "lead_name": None, "lead_email": None,
        "lead_platform": None, "lead_captured": False, "awaiting": None
    })

    state["messages"].append({"role": "user", "content": text})
    state = compiled_graph.invoke(state)
    sessions[phone] = state

    reply = next(m["content"] for m in reversed(state["messages"]) if m["role"] == "assistant")
    # ... send reply via WhatsApp API ...
    return {"status": "ok"}
```

---

## Project Structure

```
autostream-agent/
├── knowledge_base/
│   └── autostream_kb.md      # RAG source (pricing, policies)
├── agent/
│   ├── __init__.py
│   ├── state.py              # AgentState TypedDict
│   ├── nodes.py              # 5 LangGraph node functions
│   ├── graph.py              # Graph assembly + compiled_graph
│   ├── rag.py                # ChromaDB RAG pipeline
│   └── tools.py              # mock_lead_capture tool
├── chroma_db/                # Auto-created on first run
├── main.py                   # CLI entry point
├── requirements.txt
├── .env.example
└── README.md
```
