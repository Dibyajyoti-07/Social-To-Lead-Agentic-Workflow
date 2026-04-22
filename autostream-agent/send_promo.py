"""
send_promo.py — Send a proactive WhatsApp marketing message
using an approved Message Template to a list of verified numbers.

Usage:
    python send_promo.py

Place this file in autostream-agent/ alongside main.py.

Requirements:
  - An approved WhatsApp Message Template (see README / WHATSAPP_DEPLOYMENT.md)
  - Your banner image uploaded to a public URL (see Step 3 below)
  - Valid WHATSAPP_API_TOKEN and WHATSAPP_PHONE_NUMBER_ID in .env
"""

import os
import httpx
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
WHATSAPP_API_TOKEN  = os.environ["WHATSAPP_API_TOKEN"]
PHONE_NUMBER_ID     = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
WHATSAPP_API_URL    = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"

# ---------------------------------------------------------------------------
# Your approved template name and banner image URL
# Change TEMPLATE_NAME to match exactly what you named it in Meta dashboard.
# For BANNER_URL: upload your banner image to any public host
# (e.g. imgbb.com, cloudinary.com, or your own server) and paste the URL.
# ---------------------------------------------------------------------------
TEMPLATE_NAME = "autostream_promo"   # must match Meta dashboard exactly
TEMPLATE_LANGUAGE = "en"
BANNER_URL = "https://ibb.co/FbFhCPJh"  # ← replace this

# ---------------------------------------------------------------------------
# List of verified recipient numbers (international format, no + or spaces)
# These must be registered in your Meta test number list during development.
# ---------------------------------------------------------------------------
RECIPIENT_NUMBERS = [
    "917029851426",   # replace with your verified numbers
    # "919876543210",
]

# ---------------------------------------------------------------------------
# Send function
# ---------------------------------------------------------------------------
def send_template_message(to: str, recipient_name: str = "there") -> None:
    """
    Send the approved marketing template to a single recipient.
    `recipient_name` fills the {{1}} placeholder in the template body.
    """
    headers = {
        "Authorization": f"Bearer {WHATSAPP_API_TOKEN}",
        "Content-Type":  "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": TEMPLATE_NAME,
            "language": {"code": TEMPLATE_LANGUAGE},
            "components": [
                # Header component — sends your banner image
                {
                    "type": "header",
                    "parameters": [
                        {
                            "type": "image",
                            "image": {"link": BANNER_URL},
                        }
                    ],
                },
                # Body component — fills {{1}} with the recipient's name
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": recipient_name},
                    ],
                },
            ],
        },
    }

    response = httpx.post(WHATSAPP_API_URL, headers=headers, json=payload, timeout=10)

    if response.status_code in (200, 201):
        print(f"✅ Message sent to {to}")
    else:
        print(f"❌ Failed to send to {to}: {response.status_code} — {response.text}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("🚀 Sending AutoStream promo messages...\n")

    for number in RECIPIENT_NUMBERS:
        send_template_message(to=number, recipient_name="there")

    print("\n✅ Done!")