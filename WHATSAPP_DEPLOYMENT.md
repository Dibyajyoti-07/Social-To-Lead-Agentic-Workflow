# WhatsApp Deployment Guide

This guide explains how to connect the AutoStream AI Agent to WhatsApp using
Meta's Cloud API and webhooks.

---

## How It Works

```
User (WhatsApp)
      │  sends message
      ▼
Meta Cloud API
      │  POST /webhook
      ▼
webhook.py  (FastAPI)
      │  compiled_graph.invoke(state)
      ▼
AutoStream Agent  (LangGraph)
      │  produces reply
      ▼
webhook.py
      │  POST graph.facebook.com/…/messages
      ▼
Meta Cloud API
      │  delivers reply
      ▼
User (WhatsApp)
```

---

## Step 1 — Meta Developer Setup

1. Go to https://developers.facebook.com and create an app.
2. Add the **WhatsApp** product to your app.
3. In **WhatsApp → API Setup**, note down:
   - **Phone Number ID** → `WHATSAPP_PHONE_NUMBER_ID` in your `.env`
   - **Temporary access token** → `WHATSAPP_API_TOKEN` in your `.env`
     *(Generate a permanent token via System Users for production.)*
4. Add a test phone number in the **To** field and send a test message to
   confirm your token works.

---

## Step 2 — Configure Your `.env`

Copy `.env.example` to `.env` and fill in all four values:

```
GROQ_API_KEY=...
WHATSAPP_VERIFY_TOKEN=any_secret_you_choose   ← you invent this
WHATSAPP_API_TOKEN=...                         ← from Meta dashboard
WHATSAPP_PHONE_NUMBER_ID=...                   ← from Meta dashboard
```

`WHATSAPP_VERIFY_TOKEN` is a string **you make up**. You'll enter the same
value in the Meta dashboard in Step 4.

---

## Step 3 — Expose Your Server with ngrok (Local Testing)

Meta requires a **public HTTPS URL** to send webhooks to. Use ngrok during
development:

```bash
# Install ngrok from https://ngrok.com, then:
ngrok http 8000
```

Copy the `https://xxxx.ngrok-free.app` URL — you'll need it in Step 4.

---

## Step 4 — Register the Webhook in Meta

1. In your Meta App dashboard, go to **WhatsApp → Configuration**.
2. Under **Webhook**, click **Edit** and enter:
   - **Callback URL**: `https://xxxx.ngrok-free.app/webhook`
   - **Verify Token**: the same value you put in `WHATSAPP_VERIFY_TOKEN`
3. Click **Verify and Save**. Meta sends a GET request to your server;
   `webhook.py` echoes back the challenge to complete verification.
4. Under **Webhook Fields**, subscribe to **messages**.

---

## Step 5 — Run the Webhook Server

```bash
# From the autostream-agent/ directory:
uvicorn webhook:app --reload --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

---

## Step 6 — Test End-to-End

Send a WhatsApp message from your test number to the bot number. Watch the
terminal — you'll see the incoming payload logged, the agent invoked, and the
reply dispatched.

Example conversation:
```
You:   Hi!
Bot:   Hey! 👋 Welcome to AutoStream — the AI-powered video editing platform…

You:   What's the Pro plan price?
Bot:   The Pro plan is $79/month and includes unlimited videos…

You:   I want to sign up for the Pro plan for my YouTube channel.
Bot:   I'd love to get you started! 🎬 First, what's your name?

You:   Rahul
Bot:   Thanks, Rahul! What's your email address?

You:   rahul@example.com
Bot:   Almost there! Which platform do you mainly create content on?

You:   YouTube
Bot:   🎉 Thanks, Rahul! You're all set. Our team will reach out to rahul@example.com…
```

---

## Production Checklist

| Item | Notes |
|------|-------|
| Replace ngrok with a real server | Deploy to Railway, Render, or any VPS |
| Permanent Meta access token | Generate via System Users in Meta Business Manager |
| Replace `sessions` dict with Redis | `pip install redis` — use phone number as key |
| Add HTTPS | Any production host handles this automatically |
| Add request signature verification | Validate `X-Hub-Signature-256` header from Meta |

### Redis session store (drop-in replacement)

```python
import redis, json

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

def load_state(phone: str) -> AgentState:
    raw = r.get(f"session:{phone}")
    return json.loads(raw) if raw else _fresh_state()

def save_state(phone: str, state: AgentState) -> None:
    r.set(f"session:{phone}", json.dumps(state), ex=86400)  # 24h TTL
```

Replace `sessions.get(phone, _fresh_state())` and `sessions[phone] = state`
with `load_state(phone)` and `save_state(phone, state)` in `webhook.py`.

### Meta request signature verification (recommended for production)

```python
import hmac, hashlib

def _verify_signature(payload: bytes, signature_header: str, app_secret: str) -> bool:
    expected = "sha256=" + hmac.new(
        app_secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)
```

Call this at the top of `receive_message()` using the raw request body and
`request.headers.get("X-Hub-Signature-256")`.
