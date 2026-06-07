# pyrefly: ignore [missing-import]
from google import genai
# pyrefly: ignore [missing-import]
from google.genai import types
import logging
import os
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

# Initialize Client
client = genai.Client(api_key=GEMINI_API_KEY)

# Define strict Pydantic Response Schema to enforce compact output
class TradeParsingResult(BaseModel):
    type: Literal["TRADE_CALL", "UPDATE", "IGNORE"] = Field(
        description="The category of the Telegram message: TRADE_CALL, UPDATE, or IGNORE."
    )
    symbol: Optional[str] = Field(
        default=None,
        description="The trading symbol in uppercase, e.g. BTCUSDT. Strip '#' or '$'."
    )
    direction: Optional[Literal["LONG", "SHORT"]] = Field(
        default=None,
        description="The trade direction: LONG or SHORT."
    )
    entry: Optional[float] = Field(
        default=None,
        description="The entry price."
    )
    sl: Optional[float] = Field(
        default=None,
        description="Stop Loss price."
    )
    tp: Optional[List[float]] = Field(
        default=None,
        description="List of Take Profit prices."
    )
    leverage: Optional[float] = Field(
        default=None,
        description="Optional leverage if specified in text."
    )
    order_type: Optional[Literal["MARKET", "LIMIT"]] = Field(
        default=None,
        description="MARKET or LIMIT. Default to MARKET unless LIMIT is explicitly mentioned."
    )
    action: Optional[Literal["MOVE_SL", "MOVE_TP", "CLOSE_FULL", "CLOSE_PARTIAL", "BOOK_R", "CANCEL"]] = Field(
        default=None,
        description="The action for an UPDATE message."
    )
    value: Optional[str] = Field(
        default=None,
        description="The value associated with the action (e.g. 'ENTRY', 'BE', 'LIQ', or a number)."
    )
    raw_text: Optional[str] = Field(
        default=None,
        description="The specific text segment that triggered the update."
    )

PROMPT_TEMPLATE = """
Analyze the following Telegram message from a crypto trading channel.
Determine if it is a TRADE_CALL, an UPDATE, or IGNORE.

Message: "{message_text}"

Current context (if reply/edit): {reply_context}

Rules:
1. If "Booked 1R", action is BOOK_R, value is 1.
2. If "Move SL to Entry", action is MOVE_SL, value is "ENTRY".
3. If "SL to BE" or "Breakeven", action is MOVE_SL, value is "BE".
4. If "SL to Liquidation" or "SL Liq", action is MOVE_SL, value is "LIQ".
5. If "SL 69000", action is MOVE_SL, value is 69000.
6. If "Cancel" or "Delete Orders" or "Remove Limits", action is CANCEL.
7. If "TP to 65000" or "Change TP", action is MOVE_TP, value is 65000.
8. If "Market is slow", "Don't want to risk", "Closing early", "Took profit", "Took TP1", "TP1 Hit", "TP1 booked", "Profits secured", action is CLOSE_FULL.
9. "TARGET", "T1/T2/T3", "OBJECTIVE" refer to TP. "INVALIDATION", "STOP", "STOPLOSS" refer to SL.
10. Handle loose formatting.
11. If the message contains words like "idea", "observation", "watching", or "opinion" without a clear "Entry" or "SL" intent, categorize as IGNORE.
12. If a message mentions both "1R" (or profit booking) and "SL to entry" (or BE), prioritize MOVE_SL. Do NOT return BOOK_R or CLOSE_FULL if MOVE_SL is requested in the same message.
"""

async def parse_message(message_text, reply_context=""):
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=PROMPT_TEMPLATE.format(message_text=message_text, reply_context=reply_context),
            config=types.GenerateContentConfig(
                response_mime_type='application/json',
                response_schema=TradeParsingResult,
            )
        )
        
        # Safely convert Pydantic model response to standard dictionary
        parsed_obj: TradeParsingResult = response.parsed
        data = parsed_obj.model_dump()
        return data
    except Exception as e:
        logger.error(f"Error parsing message: {e}")
        return {"type": "IGNORE"}
