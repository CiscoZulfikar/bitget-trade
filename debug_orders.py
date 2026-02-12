import asyncio
import os
from dotenv import load_dotenv
import ccxt.async_support as ccxt

# Load environment variables
load_dotenv()

API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")

async def test_orders():
    exchange = ccxt.bitget({
        'apiKey': API_KEY,
        'secret': API_SECRET,
        'password': API_PASSPHRASE,
        'options': {'defaultType': 'future'}
    })

    try:
        print("Loading markets...")
        markets = await exchange.load_markets()
        print(f"Loaded {len(markets)} markets.")

        # 1. Find the CCXT symbol for BTCUSDT
        target_raw = "BTCUSDT"
        found_symbol = None
        
        for sym in markets:
            # Normalize
            clean = sym.replace("/", "").replace(":", "").split("USDT")[0] + "USDT"
            if clean == target_raw:
                found_symbol = sym
                print(f"Match found! Raw: {target_raw} -> CCXT: {found_symbol}")
                break
        
        if not found_symbol:
            print("CRITICAL: Could not find CCXT symbol for BTCUSDT")
            found_symbol = "BTC/USDT:USDT" # Guess

        # 2. Try Fetching Orders with RAW symbol
        print(f"\n--- Testing fetch_open_orders('{target_raw}') ---")
        try:
            orders_raw = await exchange.fetch_open_orders(target_raw)
            print(f"Result: Found {len(orders_raw)} orders.")
            for o in orders_raw:
                print(f" - {o['id']} ({o['type']})")
        except Exception as e:
            print(f"Result: ERROR -> {e}")

        # 3. Try Fetching Orders with CCXT symbol
        print(f"\n--- Testing fetch_open_orders('{found_symbol}') ---")
        try:
            orders_ccxt = await exchange.fetch_open_orders(found_symbol)
            print(f"Result: Found {len(orders_ccxt)} orders.")
            for o in orders_ccxt:
                print(f" - {o['id']} ({o['type']})")
        except Exception as e:
            print(f"Result: ERROR -> {e}")

    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(test_orders())
