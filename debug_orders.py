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
    
    # INSPECT CCXT METHODS
    print("\n--- Searching for 'Plan' methods in CCXT ---")
    methods = dir(handler.exchange)
    plan_methods = [m for m in methods if 'plan' in m.lower() and 'private' in m.lower()]
    
    for m in plan_methods:
        print(f"Found method: {m}")
        
    # Try the most likely candidate: privateMixGetPlanCurrentPlan or similar
    # Based on Bitget V1 vs V2 transition, names change.
    
    target_method_name = None
    # Prioritize V2
    for m in plan_methods:
        if 'v2' in m.lower() and 'pending' in m.lower():
            target_method_name = m
            break
    
    if not target_method_name and plan_methods:
        target_method_name = plan_methods[0] # Fallback
        
    if target_method_name:
        print(f"\nAttempting to call {target_method_name}...")
        method = getattr(handler.exchange, target_method_name)
        
        try:
            # Params might differ. V2 usually takes symbol + productType
            params = {
                "symbol": symbol,
                "productType": product_type
            }
            response = await method(params)
            print(f"Response: {json.dumps(response, indent=2)}")
            
        except Exception as e:
            print(f"Method call failed: {e}")
            
            # Try V1 params if V2 failed?
            # V1 often uses just 'symbol'
            try:
                print("Retrying with V1 params...")
                params_v1 = {"symbol": symbol}
                response = await method(params_v1)
                print(f"Response V1: {json.dumps(response, indent=2)}")
            except Exception as e2:
                print(f"Method call V1 failed: {e2}")

    else:
        print("No 'Plan' methods found in CCXT instance.")

    await handler.exchange.close()

if __name__ == "__main__":
    asyncio.run(debug_orders())
