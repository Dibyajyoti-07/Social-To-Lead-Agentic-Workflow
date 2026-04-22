from langgraph.graph import StateGraph, END

from agent.state import AgentState
from agent.nodes import (
    intent_classifier_node,
    rag_responder_node,
    lead_collection_node,
    lead_capture_node,
    greeting_node,
)


# ---------------------------------------------------------------------------
# Router node (passthrough — modifies no state)
# ---------------------------------------------------------------------------

def _entry_router_node(state: AgentState) -> dict:
    """
    Passthrough node. Does not modify state.
    Exists solely so we can attach a conditional edge at the very start
    of the graph, before intent classification runs.
    """
    return {}


# ---------------------------------------------------------------------------
# Routing functions (used as conditional edges)
# ---------------------------------------------------------------------------

def _entry_router(state: AgentState) -> str:
    """
    THE KEY FIX — called immediately after _entry_router_node.

    If the user is mid-lead-collection (awaiting is set to 'name', 'email',
    or 'platform'), skip intent classification entirely and go straight to
    lead_collection_node.

    Why this matters:
    Without this, every user message — including answers like "Dibyajyoti"
    or "dibyajyoti@gmail.com" — is passed through the intent classifier.
    The LLM misreads these as greetings or product inquiries and routes
    them to the wrong node, completely breaking the collection flow.
    """
    if state.get("awaiting") is not None:
        return "lead_collection"
    return "intent_classifier"


def _route_by_intent(state: AgentState) -> str:
    """Route after intent classification."""
    intent = state.get("intent", "greeting")
    if intent == "high_intent":
        return "lead_collection"
    elif intent == "product_inquiry":
        return "rag_responder"
    else:
        return "greeting"


def _route_lead_collection(state: AgentState) -> str:
    """
    After lead_collection_node runs:
    - Still awaiting a field → end the turn, wait for the user's next message.
    - All fields collected  → proceed to lead_capture.
    """
    if state.get("awaiting") is not None:
        return END
    return "lead_capture"


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # --- Register nodes ---
    graph.add_node("router",            _entry_router_node)
    graph.add_node("intent_classifier", intent_classifier_node)
    graph.add_node("rag_responder",     rag_responder_node)
    graph.add_node("lead_collection",   lead_collection_node)
    graph.add_node("lead_capture",      lead_capture_node)
    graph.add_node("greeting",          greeting_node)

    # --- Entry point is now the router, not intent_classifier ---
    graph.set_entry_point("router")

    # Router: bypass intent classifier when mid-collection
    graph.add_conditional_edges(
        "router",
        _entry_router,
        {
            "intent_classifier": "intent_classifier",
            "lead_collection":   "lead_collection",
        },
    )

    # After intent classification, route by detected intent
    graph.add_conditional_edges(
        "intent_classifier",
        _route_by_intent,
        {
            "greeting":        "greeting",
            "rag_responder":   "rag_responder",
            "lead_collection": "lead_collection",
        },
    )

    # Terminal nodes → END
    graph.add_edge("greeting",      END)
    graph.add_edge("rag_responder", END)

    # Lead collection loop / capture gate
    graph.add_conditional_edges(
        "lead_collection",
        _route_lead_collection,
        {
            END:            END,
            "lead_capture": "lead_capture",
        },
    )

    graph.add_edge("lead_capture", END)

    return graph


# Compiled graph — imported by main.py and webhook.py
compiled_graph = build_graph().compile()