import asyncio
from exchange_handler import ExchangeHandler
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_status():
    print("Initializing Exchange Handler...")
    handler = ExchangeHandler()
    
    print("\n--- Testing get_balance ---")
    try:
        # Try default
        print("Calling fetch_balance()...")
        balance = await handler.exchange.fetch_balance()
        print("Balance Keys:", list(balance.keys()))
        if 'USDT' in balance:
            print("USDT Balance:", balance['USDT'])
        else:
            print("USDT not found in balance!")
            print("Full Balance:", balance)
            
    except Exception as e:
        print(f"❌ fetch_balance failed: {e}")

    print("\n--- Testing get_all_positions ---")
    try:
        print("Calling fetch_positions()...")
        # Try with explicit type if needed
        positions = await handler.exchange.fetch_positions()
        print(f"Found {len(positions)} positions.")
        for p in positions:
            if float(p['contracts']) > 0:
                print(f" - {p['symbol']}: {p['contracts']} contracts")
    except Exception as e:
        print(f"❌ fetch_positions failed: {e}")

    print("\n--- Testing Explicit Swap Params ---")
    try:
        print("Calling fetch_balance(params={'type': 'swap'})...")
        balance = await handler.exchange.fetch_balance(params={'type': 'swap'})
        print("USDT Equity:", balance.get('USDT', {}).get('total'))
    except Exception as e:
        print(f"❌ Explicit fetch_balance failed: {e}")

    await handler.close()

if __name__ == "__main__":
    asyncio.run(debug_status())
