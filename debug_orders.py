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
    try:
        await handler.exchange.load_markets()
    except Exception:
        pass
    
    # ASK USER FOR SYMBOL
    symbol = input("Enter symbol to debug (e.g. BTCUSDT): ").strip().upper()
    if not symbol.endswith("USDT") and ":" not in symbol: symbol += "USDT"
    
    # Map to Bitget Product Type
    product_type = "USDT-FUTURES" 
    
    print(f"Fetching Plan Orders for {symbol}...")
    
    try:
        # Based on Bitget V2 API Docs for /api/v2/mix/order/orders-plan-pending:
        # Required: productType, planType
        # planType options: 'profit_loss' (TP/SL), 'normal_plan' (Trigger)
        
        params = {
            "symbol": symbol,
            "productType": product_type,
            "planType": "profit_loss", # This is likely the missing key!
        }
        
        # CCXT Method found in previous step: privateMixGetV2MixOrderOrdersPlanPending
        if hasattr(handler.exchange, 'privateMixGetV2MixOrderOrdersPlanPending'):
            print(f"Calling privateMixGetV2MixOrderOrdersPlanPending with {params}...")
            response = await handler.exchange.privateMixGetV2MixOrderOrdersPlanPending(params)
            
            if response['code'] == '00000':
                data = response['data']['entrustedList']
                print(f"\nFound {len(data)} Plan Orders:")
                for i, o in enumerate(data):
                    print(f"\n--- Plan Order {i+1} ---")
                    print(f"PlanType: {o.get('planType')}")
                    print(f"TriggerPrice: {o.get('triggerPrice')}")
                    print(f"Side: {o.get('side')}")
                    print(f"Status: {o.get('status')}")
                    print(f"Raw: {json.dumps(o, indent=2)}")
            else:
                print(f"API Error: {response}")
        else:
            print("Method privateMixGetV2MixOrderOrdersPlanPending not found (unexpected).")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await handler.exchange.close()

if __name__ == "__main__":
    asyncio.run(debug_orders())
