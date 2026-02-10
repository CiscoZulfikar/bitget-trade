
import asyncio
import logging
from exchange_handler import ExchangeHandler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_mode():
    exchange = ExchangeHandler()
    symbol = "BTCUSDT"
    
    try:
        print(f"--- Checking Mode for {symbol} ---")
        
        # 1. Fetch Position Mode
        # CCXT uses privateMixGetV2MixAccountAccountAccount to get margin/pos mode often
        # Or implicit
        try:
            mode = await exchange.exchange.fetch_position_mode(symbol)
            print(f"Current Mode (CCXT): {mode}")
        except Exception as e:
            print(f"CCXT fetch_position_mode failed: {e}")

        # 2. Try Raw API check if needed
        # (CCXT usually reliable for this)
        
        print("\n--- Attempting to Set Hedge Mode (True) ---")
        try:
            resp = await exchange.exchange.set_position_mode(True, symbol)
            print(f"Set Hedge Mode Result: {resp}")
        except Exception as e:
            print(f"Set Hedge Mode Failed: {e}")

        print("\n--- Re-Checking Mode ---")
        try:
            mode = await exchange.exchange.fetch_position_mode(symbol)
            print(f"Current Mode (CCXT): {mode}")
        except Exception as e:
            print(f"CCXT fetch_position_mode failed: {e}")

    except Exception as e:
        print(f"General Error: {e}")
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(check_mode())
