from google import genai
from google.genai import types
import logging
import json
import os
from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

# Initialize Client
client = genai.Client(api_key=GEMINI_API_KEY)

PROMPT_TEMPLATE = """
Analyze the following Telegram message from a crypto trading channel.
Determine if it is a TRADE_CALL, an UPDATE, or IGNORE.

Message: "{message_text}"

Current context (if reply/edit): {reply_context}

Output strictly in JSON format.

If TRADE_CALL:
{{
  "type": "TRADE_CALL",
  "symbol": "BTCUSDT", (Strip '#' or '$'. Always uppercase.)
  "direction": "LONG" or "SHORT",
  "entry": float,
  "sl": float,
  "tp": [float, float...] (optional list),
  "leverage": float (optional, if specified),
  "order_type": "MARKET" or "LIMIT" (Default to MARKET unless "LIMIT" is explicitly mentioned in text)
}}

If UPDATE (e.g., "Booked 1R", "Booked 2.5R", "Move SL to Entry", "Close Half", "SL Hit"):
{{
  "type": "UPDATE",
  "action": "MOVE_SL" or "CLOSE_FULL" or "CLOSE_PARTIAL" or "BOOK_R",
  "value": float (e.g. new SL price, or the R multiple number if Booking R),
  "raw_text": "original text segment"
}}

If IGNORE (news, fluff, marketing):
{{
  "type": "IGNORE"
}}

Rules:
1. If "Booked 1R", action is BOOK_R, value is 1.
2. If "Booked 0.5R", action is BOOK_R, value is 0.5.
3. "Move SL to Entry" means new SL = original Entry.
4. Handle loose formatting.
"""

async def parse_message(message_text, reply_context=""):
    try:
        # Using the new models.generate_content method from google-genai
        response = client.models.generate_content(
            model='gemini-2.5-flash', # Switching to Gemini 2.5 Flash as confirmed available
            contents=PROMPT_TEMPLATE.format(message_text=message_text, reply_context=reply_context),
            config=types.GenerateContentConfig(
                response_mime_type='application/json'
            )
        )
        
        text = response.text.strip()
        data = json.loads(text)
        return data
    except Exception as e:
        logger.error(f"Error parsing message: {e}")
        return {"type": "IGNORE"}
