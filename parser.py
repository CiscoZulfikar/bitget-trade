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
  "sl": float (Look for 'SL', 'STOP LOSS', 'STOP', 'INVALIDATION', '❌'),
  "tp": [float, float...] (Take Profit levels. Look for 'TP', 'TARGET', 'T1', 'T2', 'TAKE PROFIT', '🎯'),
  "leverage": float (optional, if specified),
  "order_type": "MARKET" or "LIMIT" (Default to MARKET unless "LIMIT" is explicitly mentioned in text)
}}

If UPDATE (e.g., "Booked 1R", "Booked 2.5R", "Move SL to Entry", "Close Half", "SL Hit", "Closing $COIN here", "Cancel Orders", "Delete Limits", "TP to 65000", "Change TP"):
{{
  "type": "UPDATE",
  "symbol": "BTCUSDT", (Optional. If not in message, INFER from context/reply chain. Strip #/$)
  "action": "MOVE_SL" or "MOVE_TP" or "CLOSE_FULL" or "CLOSE_PARTIAL" or "BOOK_R" or "CANCEL",
  "value": float OR string ("ENTRY", "BE", "LIQ") if applicable,
  "raw_text": "original text segment" (e.g. "Target 1 Hit")
}}

If IGNORE (news, fluff, marketing):
{{
  "type": "IGNORE"
}}

Rules:
1. If "Booked 1R", action is BOOK_R, value is 1.
2. If "Move SL to Entry", action is MOVE_SL, value is "ENTRY".
3. If "SL to BE" or "Breakeven", action is MOVE_SL, value is "BE".
4. If "SL to Liquidation" or "SL Liq", action is MOVE_SL, value is "LIQ".
5. If "SL 69000", action is MOVE_SL, value is 69000.
6. If "Cancel" or "Delete Orders" or "Remove Limits", action is CANCEL.
7. If "TP to 65000" or "Change TP", action is MOVE_TP, value is 65000.
8. "TARGET", "T1/T2/T3", "OBJECTIVE" refer to TP. "INVALIDATION", "STOP", "STOPLOSS" refer to SL.
9. Handle loose formatting.
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
