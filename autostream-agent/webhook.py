"""
webhook.py — FastAPI WhatsApp webhook server for the AutoStream AI Agent.

Handles two types of requests from Meta:
  GET  /webhook  — verification handshake (one-time setup)
  POST /webhook  — incoming WhatsApp messages

Per-user AgentState is stored in an in-memory dict keyed by phone number.
Swap `sessions` for a Redis/DB store for production multi-process deployments.
"""

import os
import logging
import httpx

from fastapi import FastAPI, Request, Response, HTTPException
from dotenv import load_dotenv

from agent.graph import compiled_graph
from agent.state import AgentState

load_dotenv()

# ---------------------------------------------------------------------------
# Config — all values come from .env
# ---------------------------------------------------------------------------
VERIFY_TOKEN        = os.environ["WHATSAPP_VERIFY_TOKEN"]       # any secret string you choose
WHATSAPP_API_TOKEN  = os.environ["WHATSAPP_API_TOKEN"]          # Meta permanent / temp access token
PHONE_NUMBER_ID     = os.environ["WHATSAPP_PHONE_NUMBER_ID"]    # from Meta Developer dashboard

WHATSAPP_API_URL = (
    f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
)

# ---------------------------------------------------------------------------
# App + logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="AutoStream WhatsApp Agent")

# In-memory session store: phone_number (str) → AgentState
sessions: dict[str, AgentState] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_state() -> AgentState:
    """Return a clean initial AgentState for a new user."""
    return {
        "messages":      [],
        "intent":        None,
        "lead_name":     None,
        "lead_email":    None,
        "lead_platform": None,
        "lead_captured": False,
        "awaiting":      None,
    }


def _last_assistant_message(state: AgentState) -> str | None:
    """Extract the most recent assistant message from state."""
    for msg in reversed(state["messages"]):
        if msg["role"] == "assistant":
            return msg["content"]
    return None


async def _send_whatsapp_message(to: str, text: str) -> None:
    """
    Send a text message to a WhatsApp user via the Meta Cloud API.
    Raises an exception if the API returns a non-2xx status.
    """
    headers = {
        "Authorization": f"Bearer {WHATSAPP_API_TOKEN}",
        "Content-Type":  "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to":                to,
        "type":              "text",
        "text":              {"body": text},
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(WHATSAPP_API_URL, headers=headers, json=payload)

    if resp.status_code not in (200, 201):
        log.error("WhatsApp API error %s: %s", resp.status_code, resp.text)
        resp.raise_for_status()

    log.info("Message sent to %s", to)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/webhook")
async def verify_webhook(request: Request) -> Response:
    """
    Meta sends a GET request to verify the webhook endpoint.
    We must echo back the hub.challenge value if the verify token matches.

    Meta query params:
      hub.mode         — always "subscribe"
      hub.verify_token — the secret token you set in the Meta dashboard
      hub.challenge    — a random string we must return verbatim
    """
    params = request.query_params
    mode      = params.get("hub.mode")
    token     = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        log.info("Webhook verified successfully.")
        return Response(content=challenge, media_type="text/plain")

    log.warning("Webhook verification failed. Token mismatch or wrong mode.")
    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/webhook")
async def receive_message(request: Request) -> dict:
    """
    Meta sends a POST for every incoming WhatsApp message.

    Payload structure (simplified):
    {
      "object": "whatsapp_business_account",
      "entry": [{
        "changes": [{
          "value": {
            "messages": [{
              "from": "<phone_number>",
              "type": "text",
              "text": { "body": "<message_text>" }
            }]
          }
        }]
      }]
    }
    """
    body = await request.json()
    log.debug("Incoming payload: %s", body)

    # --- Extract message details ---
    try:
        changes  = body["entry"][0]["changes"][0]["value"]
        messages = changes.get("messages")

        # Ignore status updates (delivery receipts, read receipts, etc.)
        if not messages:
            return {"status": "ignored"}

        message = messages[0]

        # Only handle plain text messages
        if message.get("type") != "text":
            log.info("Non-text message type '%s' ignored.", message.get("type"))
            return {"status": "ignored"}

        phone    = message["from"]           # e.g. "919876543210"
        text     = message["text"]["body"].strip()

    except (KeyError, IndexError, TypeError) as exc:
        log.error("Failed to parse webhook payload: %s", exc)
        # Return 200 so Meta doesn't retry — we just couldn't parse it
        return {"status": "parse_error"}

    log.info("Message from %s: %s", phone, text)

    # --- Load or create session state ---
    state = sessions.get(phone, _fresh_state())

    # If the lead is already captured, send a polite closure message
    if state.get("lead_captured"):
        await _send_whatsapp_message(
            phone,
            "You're already registered with us! 🎉 Our team will be in touch soon.",
        )
        return {"status": "ok"}

    # --- Append user turn and invoke the agent ---
    state["messages"].append({"role": "user", "content": text})

    try:
        state = compiled_graph.invoke(state)
    except Exception as exc:
        log.error("Agent error for %s: %s", phone, exc, exc_info=True)
        await _send_whatsapp_message(
            phone,
            "Sorry, something went wrong on our end. Please try again in a moment. 🙏",
        )
        return {"status": "agent_error"}

    # --- Persist updated state ---
    sessions[phone] = state

    # --- Send the agent's reply ---
    reply = _last_assistant_message(state)
    if reply:
        await _send_whatsapp_message(phone, reply)

    return {"status": "ok"}