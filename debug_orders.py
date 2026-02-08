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
    
    # Bypass loading markets
    handler.exchange.options['fetchMarkets'] = ['swap']
    
    # FORCE IT:
    try:
        await handler.exchange.load_markets()
    except Exception as e:
        print(f"Load markets warning: {e}")
    
    # ASK USER FOR SYMBOL
    symbol = input("Enter symbol to debug (e.g. BTCUSDT): ").strip().upper()
    if not symbol.endswith("USDT") and ":" not in symbol: symbol += "USDT"
    
    print(f"Fetching Open Orders & Plan Orders for {symbol}...")
    try:
        # 1. Standard Open Orders (Limit orders in book)
        print("\n--- 1. FETCH OPEN ORDERS (Standard) ---")
        orders = await handler.exchange.fetch_open_orders(symbol)
        print(f"Found {len(orders)} Standard Orders")
        for o in orders:
            print(f"ID: {o['id']} | Type: {o['type']} | Price: {o.get('price')} | Stop: {o.get('stopPrice')}")

        # 2. Trigger/Plan Orders (SL/TP usually live here)
        print("\n--- 2. FETCH OPEN ORDERS (Trigger/Plan) ---")
        # CCXT bitget uses params request to get plan orders
        # Bitget V2: mix/plan/current-plan
        
        # Try passing params to fetch_open_orders
        # Some exchanges support 'trigger': True
        orders_trigger = await handler.exchange.fetch_open_orders(symbol, params={'stop': True}) # generic CCXT param?
        
        # If that doesn't work, try raw Bitget V2 endpoint for plan orders
        if not orders_trigger:
             print(" ... Trying raw CCXT fetch_open_orders with Bitget specific params ...")
             # Bitget specific: productType, ...
             # Actually, let's try 'trigger': True which CCXT might map
             orders_trigger = await handler.exchange.fetch_open_orders(symbol, params={'trigger': True})
        
        # If CCXT mapping fails, let's try implicit API method if available, or direct request
        if not orders_trigger and hasattr(handler.exchange, 'fetch_trigger_orders'):
             pass # checks later

        print(f"Found {len(orders_trigger)} Trigger Orders (via params)")
        for i, o in enumerate(orders_trigger):
            print(f"\n--- Trigger Order {i+1} ---")
            print(f"ID: {o['id']}")
            print(f"Type: {o['type']}")
            print(f"Side: {o['side']}")
            print(f"StopPrice: {o.get('stopPrice')}")
            print(f"TriggerPrice: {o.get('triggerPrice')}")
            print(f"Info: {json.dumps(o.get('info', {}), indent=2)}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await handler.exchange.close()

if __name__ == "__main__":
    asyncio.run(debug_orders())
