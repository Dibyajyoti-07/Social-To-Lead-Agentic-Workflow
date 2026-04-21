from typing import TypedDict, Optional, List


class AgentState(TypedDict):
    messages: List[dict]          # Full conversation history: [{"role": ..., "content": ...}]
    intent: Optional[str]         # "greeting" | "product_inquiry" | "high_intent"
    lead_name: Optional[str]
    lead_email: Optional[str]
    lead_platform: Optional[str]
    lead_captured: bool
    awaiting: Optional[str]       # "name" | "email" | "platform" | None

