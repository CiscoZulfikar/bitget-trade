import asyncio
import os
import logging
from exchange_handler import ExchangeHandler

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ManualClose")

async def main():
    print("--- 🔍 Checking Positions ---")
    handler = ExchangeHandler()
    
    # 1. Fetch All Positions
    positions = await handler.get_all_positions()
    
    if not positions:
        print("✅ No open positions found on exchange.")
        await handler.close()
        return

    print(f"⚠️ Found {len(positions)} Open Positions:")
    for p in positions:
        print(f"   - {p['symbol']}: {p['side'].upper()} | Size: {p['contracts']} | PnL: {p['unrealizedPnl']}")

    # 2. Ask to Close
    # Since this is non-interactive in this env, we will try to close 'TIAUSDT' if found, 
    # as that was the problematic one.
    
    target = "TIAUSDT"
    target_pos = next((p for p in positions if target in p['symbol']), None)
    
    if target_pos:
        print(f"\n--- 🔴 Attempting to Close {target} ---")
        success = await handler.close_position(target_pos['symbol'])
        if success:
            print(f"✅ SUCCESSFULLY CLOSED {target}.")
        else:
            print(f"❌ FAILED TO CLOSE {target}.")
    else:
        print(f"\nℹ️ {target} not found in open positions. (It might be already closed)")

    await handler.close()

if __name__ == "__main__":
    asyncio.run(main())
