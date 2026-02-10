import asyncio
from exchange_handler import ExchangeHandler
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_validation():
    print("Initializing Exchange Handler...")
    handler = ExchangeHandler()
    
    test_cases = [
        "BTC",          # Should be BTCUSDT
        "ETH",          # Should be ETHUSDT
        "BONK",         # Should be 1000BONKUSDT (or similar)
        "PEPE",         # Should be 1000PEPEUSDT
        "SHIB",         # Should be 1000SHIBUSDT
        "WIF",          # Should be WIFUSDT
        "$DOGE",        # Should be DOGEUSDT
        "XRP#",         # Should be XRPUSDT
        "UNKNOWNCOIN"   # Should default to UNKNOWNCOINUSDT
    ]
    
    print("\n--- Testing Symbol Validation ---")
    try:
        # Pre-load markets to ensure we don't hit rate limits in loop
        await handler.exchange.load_markets()
        print(f"Loaded {len(handler.exchange.markets)} markets.")

        # DEBUG: Print exact keys for BONK and PEPE
        print("\n--- Market Keys Debug ---")
        for key in handler.exchange.markets.keys():
            if "BONK" in key or "PEPE" in key:
                print(f"Found Market Key: {key} -> ID: {handler.exchange.markets[key]['id']}")
        print("-------------------------\n")
        
        for input_sym in test_cases:
            resolved = await handler.validate_symbol(input_sym)
            print(f"❌ Input: {input_sym.ljust(12)} -> ✅ Resolved: {resolved}")
            
    except Exception as e:
        print(f"❌ Validation failed: {e}")

    await handler.close()

if __name__ == "__main__":
    asyncio.run(debug_validation())
