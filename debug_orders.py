import asyncio
from exchange_handler import ExchangeHandler
import json
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_orders():
    print("Initializing Exchange Handler...")
    handler = ExchangeHandler()
    
    # Bypass loading markets
    handler.exchange.options['fetchMarkets'] = ['swap']
    try:
        await handler.exchange.load_markets()
    except Exception:
        pass
    
    # ASK USER FOR SYMBOL
    symbol = input("Enter symbol to debug (e.g. BTCUSDT): ").strip().upper()
    if not symbol.endswith("USDT") and ":" not in symbol: symbol += "USDT"
    
    # Map to Bitget Product Type
    product_type = "USDT-FUTURES" 
    
    print(f"Fetching RAW Plan Orders for {symbol} ({product_type})...")
    
    try:
        # RAW API CALL to Bitget V2
        # Endpoint: /api/v2/mix/order/orders-plan-pending
        endpoint = "/api/v2/mix/order/orders-plan-pending"
        params = {
            "symbol": symbol,
            "productType": product_type
        }
        
        print(f"Requesting {endpoint} with {params}...")
        
        # Use CCXT's internal private request method to handle signing
        response = await handler.exchange.request(endpoint, api='v2', method='GET', params=params)
        
        if response['code'] == '00000':
            data = response['data']['entrustedList']
            print(f"\nFound {len(data)} Plan Orders (RAW API):")
            for i, o in enumerate(data):
                print(f"\n--- Plan Order {i+1} ---")
                print(f"PlanType: {o.get('planType')}")
                print(f"TriggerPrice: {o.get('triggerPrice')}")
                print(f"ExecutePrice: {o.get('executePrice')}")
                print(f"Side: {o.get('side')}")
                print(f"Status: {o.get('status')}")
                print(f"Raw: {json.dumps(o, indent=2)}")
        else:
            print(f"API Error: {response}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await handler.exchange.close()

if __name__ == "__main__":
    asyncio.run(debug_orders())
