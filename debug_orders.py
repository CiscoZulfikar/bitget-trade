import asyncio
from exchange_handler import ExchangeHandler
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_orders():
    print("Initializing Exchange Handler...")
    handler = ExchangeHandler()
    
    # Bypass loading markets to avoid Spot API errors
    handler.exchange.options['fetchMarkets'] = ['linear'] # Only linear futures
    # handler.exchange.load_markets = lambda: None # DANGEROUS hack, better to just catch error?
    # Actually, ExchangeHandler init already disables fetchCurrencies.
    # The error 'v2/spot/public/symbols' comes from load_markets().
    # Let's wrap the fetch in a try/except that ignores market loading issues if possible
    # OR better: just don't call anything that triggers it? 
    # fetch_open_orders usually triggers load_markets.
    
    # FORCE IT:
    await handler.exchange.load_markets() # If this fails, we catch it?
    
    # ASK USER FOR SYMBOL
    symbol = input("Enter symbol to debug (e.g. BTCUSDT): ").strip().upper()
    if not symbol.endswith("USDT"): symbol += "USDT"
    
    print(f"Fetching Open Orders for {symbol}...")
    try:
        # Fetch raw open orders to see structure
        orders = await handler.exchange.fetch_open_orders(symbol)
        
        print(f"\nFound {len(orders)} Open Orders:")
        
        for i, o in enumerate(orders):
            print(f"\n--- Order {i+1} ---")
            # Print Key Fields
            print(f"ID: {o['id']}")
            print(f"Type: {o['type']}")
            print(f"Side: {o['side']}")
            print(f"Price: {o.get('price')}")
            print(f"StopPrice: {o.get('stopPrice')}")
            print(f"TriggerPrice: {o.get('triggerPrice')}")
            print(f"Status: {o['status']}")
            
            # Print 'info' which contains raw exchange response
            print(f"Raw 'info': {json.dumps(o.get('info', {}), indent=2)}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await handler.exchange.close()

if __name__ == "__main__":
    asyncio.run(debug_orders())
