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
# Routing functions (used as conditional edges)
# ---------------------------------------------------------------------------

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
    - If still awaiting a field → end the turn and wait for the user's reply.
      (Returning END stops the graph so the next graph.invoke() call brings
      the user's actual answer, preventing the previous turn's message from
      being mis-stored as a lead field.)
    - If all fields are collected (awaiting is None) → go to lead_capture.
    """
    if state.get("awaiting") is not None:
        return END   # Stop here; resume on next user message
    return "lead_capture"


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("intent_classifier", intent_classifier_node)
    graph.add_node("rag_responder", rag_responder_node)
    graph.add_node("lead_collection", lead_collection_node)
    graph.add_node("lead_capture", lead_capture_node)
    graph.add_node("greeting", greeting_node)

    # Entry point
    graph.set_entry_point("intent_classifier")

    # Conditional routing after intent classification
    graph.add_conditional_edges(
        "intent_classifier",
        _route_by_intent,
        {
            "greeting": "greeting",
            "rag_responder": "rag_responder",
            "lead_collection": "lead_collection",
        },
    )

    # Terminal nodes → END
    graph.add_edge("greeting", END)
    graph.add_edge("rag_responder", END)

    # Lead collection: end the turn while waiting for a field,
    # or proceed to capture once all fields are collected.
    graph.add_conditional_edges(
        "lead_collection",
        _route_lead_collection,
        {
            END: END,
            "lead_capture": "lead_capture",
        },
    )

    graph.add_edge("lead_capture", END)

    return graph


# Compiled graph — imported by main.py
compiled_graph = build_graph().compile()