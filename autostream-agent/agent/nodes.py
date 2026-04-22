import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from agent.state import AgentState
from agent.rag import retrieve
from agent.tools import mock_lead_capture

load_dotenv()


_llm = ChatGroq(
    model_name="llama-3.3-70b-versatile",
    groq_api_key=os.environ.get("GROQ_API_KEY"),
    temperature=0.3,
)


def _get_last_user_message(state: AgentState) -> str:
    """Helper: extract the last user message from the conversation history."""
    for msg in reversed(state["messages"]):
        if msg["role"] == "user":
            return msg["content"]
    return ""


# ---------------------------------------------------------------------------
# Node 1: Intent Classifier
# ---------------------------------------------------------------------------
def intent_classifier_node(state: AgentState) -> dict:
    """
    Classify the last user message into one of:
    greeting | product_inquiry | high_intent
    """
    user_msg = _get_last_user_message(state)

    system_prompt = (
        "You are an intent classifier for AutoStream, a SaaS video editing platform.\n"
        "Classify the user message into EXACTLY one of these labels:\n"
        "  - greeting       → casual hello, hi, how are you, etc.\n"
        "  - product_inquiry → questions about pricing, plans, features, support, policies\n"
        "  - high_intent    → user wants to sign up, buy, try, start a trial, or subscribe\n\n"
        "Reply with ONLY the label. No punctuation, no explanation."
    )

    response = _llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_msg),
    ])

    raw = response.content.strip().lower()

    # Normalise — handle slight variations from the LLM
    if "high" in raw:
        intent = "high_intent"
    elif "product" in raw or "inquiry" in raw:
        intent = "product_inquiry"
    else:
        intent = "greeting"

    return {"intent": intent}


# ---------------------------------------------------------------------------
# Node 2: RAG Responder
# ---------------------------------------------------------------------------
def rag_responder_node(state: AgentState) -> dict:
    """
    Retrieve relevant context from ChromaDB and ask the LLM to answer
    the user's question based ONLY on that context.
    """
    user_msg = _get_last_user_message(state)
    context = retrieve(user_msg)

    system_prompt = (
        "You are a helpful support agent for AutoStream, a SaaS video editing platform.\n"
        "Answer the user's question using ONLY the context provided below.\n"
        "If the context does not contain the answer, say: "
        "'I don't have that information right now. Please contact our support team.'\n"
        "Be concise and friendly.\n\n"
        f"Context:\n{context}"
    )

    response = _llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_msg),
    ])

    answer = response.content.strip()
    updated_messages = state["messages"] + [{"role": "assistant", "content": answer}]
    return {"messages": updated_messages}


# ---------------------------------------------------------------------------
# Node 3: Lead Collection
# ---------------------------------------------------------------------------
def lead_collection_node(state: AgentState) -> dict:
    """
    Collect missing lead fields (name → email → platform) one at a time.
    On each turn:
      - If we are 'awaiting' a field, store the last user message into that field.
      - Then determine the next missing field and ask for it.
      - If all fields are collected, just return without asking (graph will route to capture).
    """
    user_msg = _get_last_user_message(state)

    # --- Store the answer for the field we were awaiting ---
    updates: dict = {}
    awaiting = state.get("awaiting")

    if awaiting == "name":
        updates["lead_name"] = user_msg
    elif awaiting == "email":
        # Basic email validation before accepting
        if "@" not in user_msg or "." not in user_msg:
            question = "That doesn't look like a valid email address. Could you double-check it? 📧"
            updated_messages = state["messages"] + [{"role": "assistant", "content": question}]
            return {"awaiting": "email", "messages": updated_messages}
        updates["lead_email"] = user_msg
    elif awaiting == "platform":
        updates["lead_platform"] = user_msg

    # Compute effective values after applying updates
    name     = updates.get("lead_name",     state.get("lead_name"))
    email    = updates.get("lead_email",    state.get("lead_email"))
    platform = updates.get("lead_platform", state.get("lead_platform"))

    # --- Determine the next missing field ---
    if not name:
        next_awaiting = "name"
        question = (
            "I'd love to get you started with AutoStream! 🎬\n"
            "First, what's your name?"
        )
    elif not email:
        next_awaiting = "email"
        question = f"Thanks, {name}! What's your email address?"
    elif not platform:
        next_awaiting = "platform"
        question = (
            f"Almost there! Which platform do you mainly create content on? "
            "(e.g. YouTube, Instagram, TikTok, etc.)"
        )
    else:
        # All collected — signal to graph that we're done collecting
        next_awaiting = None
        question = None

    if question:
        updated_messages = state["messages"] + [{"role": "assistant", "content": question}]
        return {
            **updates,
            "awaiting": next_awaiting,
            "messages": updated_messages,
        }

    # All fields are ready — no message appended; lead_capture_node will respond
    return {
        **updates,
        "awaiting":      None,
        "lead_name":     name,
        "lead_email":    email,
        "lead_platform": platform,
    }


# ---------------------------------------------------------------------------
# Node 4: Lead Capture
# ---------------------------------------------------------------------------
def lead_capture_node(state: AgentState) -> dict:
    """
    Call mock_lead_capture with all three collected fields and confirm to user.
    Only reached when name, email, and platform are all non-empty.
    """
    name     = state["lead_name"]
    email    = state["lead_email"]
    platform = state["lead_platform"]

    # Fire the mock tool
    mock_lead_capture(name, email, platform)

    confirmation = (
        f"🎉 Thanks, {name}! You're all set.\n"
        f"Our team will reach out to {email} very soon to get you started with AutoStream. "
        f"We can't wait to see your {platform} content level up! 🚀"
    )

    updated_messages = state["messages"] + [{"role": "assistant", "content": confirmation}]
    return {
        "messages":      updated_messages,
        "lead_captured": True,
    }


# ---------------------------------------------------------------------------
# Node 5: Greeting
# ---------------------------------------------------------------------------
def greeting_node(state: AgentState) -> dict:
    """
    Respond with a warm, branded greeting about AutoStream.
    """
    user_msg = _get_last_user_message(state)

    system_prompt = (
        "You are a friendly and enthusiastic assistant for AutoStream — "
        "an AI-powered SaaS platform for video creators.\n"
        "Greet the user warmly and briefly mention that AutoStream helps creators "
        "edit videos faster with AI. Keep it to 2-3 sentences max."
    )

    response = _llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_msg),
    ])

    answer = response.content.strip()
    updated_messages = state["messages"] + [{"role": "assistant", "content": answer}]
    return {"messages": updated_messages}