
import asyncio
import os
import logging
from exchange_handler import ExchangeHandler
from dotenv import load_dotenv

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("debug_tpsl")

async def main():
    load_dotenv()
    
    exchange = ExchangeHandler()
    print("Exchange Handler Initialized.")
    
    # HARDCODED TEST - CHANGE THESE IF NEEDED
    symbol = "ETH/USDT:USDT"
    target_sl = 2000.0 
    
    print(f"Testing Update SL for {symbol} to {target_sl}...")
    
    try:
        # We will try to call update_sl directly
        # valid methods: place_order, get_position, update_sl
        
        # 1. Check Position first
        pos = await exchange.get_position(symbol)
        print(f"Current Position: {pos}")
        
        if not pos:
            print("⚠️ NO POSITION FOUND! Cannot test Position SL update.")
            print("Please open a small position on ETHUSDT first.")
            return

        # 2. Call Update SL
        success, msg = await exchange.update_sl(symbol, target_sl)
        print(f"Result: Success={success}, Msg={msg}")
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(main())
