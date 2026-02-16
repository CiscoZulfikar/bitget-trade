
import asyncio
import os
import ccxt.async_support as ccxt
from dotenv import load_dotenv
import json

# Load params
load_dotenv()
API_KEY = os.getenv("BITGET_API_KEY")
SECRET = os.getenv("BITGET_SECRET_KEY")
PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

async def main():
    print("--- DEBUGGING GHOST SL ---")
    exchange = ccxt.bitget({
        'apiKey': API_KEY,
        'secret': SECRET,
        'password': PASSPHRASE,
        'options': {'defaultType': 'swap'},
    })

    symbol = "ETHUSDT"
    
    # 1. Inspect Position Raw Data
    print("\n[1] Inspecting Position Raw Data...")
    try:
        positions = await exchange.fetch_positions([symbol])
        for p in positions:
            print(f"Position Info for {p['symbol']}:")
            # Print the FULL 'info' dictionary which contains the raw exchange response
            print(json.dumps(p['info'], indent=2)) 
            
            # Check for specific SL fields
            info = p['info']
            if 'stopLossPrice' in info:
                print(f"Found 'stopLossPrice' in info: {info['stopLossPrice']}")
    except Exception as e:
        print(f"Error fetching position: {e}")

    # 2. Try Manual Request to set-stop-order
    # This bypasses CCXT's missing method definition
    print("\n[2] Attempting Manual Request to /api/v2/mix/position/set-stop-order...")
    
    # We want to TRY to set the SL to the NEW valid price (e.g. 1970.82)
    # If this works, it might overwrite the 'Ghost' Position SL.
    new_sl = "1970.82"
    
    try:
        # Define params
        params = {
            "symbol": "ETHUSDT",
            "productType": "USDT-FUTURES",
            "marginCoin": "USDT",
            "stopLoss": new_sl, 
            "holdSide": "short" # Assuming short based on logs, adjust if needed
        }
        
        # CCXT 'request' method: request(path, api='public'|'private', method='GET'|'POST', params={}, headers=None, body=None)
        # For Bitget v2, paths usually exclude the /api/v2 part if using specific 'api' keys in urls definition, 
        # but using the generic 'request' usually requires relative path handling.
        # Let's try the implicit access via 'private' property which handles signing.
        
        # Actually, let's try to inject the call if possible.
        # exchange.sign(...) is internal.
        
        # Alternative: implicit 'v2' accessor?
        # exchange.privatePostMixPositionSetStopOrder(params) ??
        # The list didn't show it.
        
        # We will try a different implicit name structure just in case the list was incomplete OR
        # Try to use 'request'
        
        response = await exchange.request('mix/position/set-stop-order', api='v2', method='POST', params=params)
        print("✅ Manual Request SUCCESS:")
        print(json.dumps(response, indent=2))
        
    except Exception as e:
        print(f"❌ Manual Request FAILED: {e}")
        # Try 'private' api fallback
        try:
             print("Retrying with 'mix' api prefix...")
             response = await exchange.request('v2/mix/position/set-stop-order', api='mix', method='POST', params=params) 
             print("✅ Manual Request SUCCESS (Attempt 2):")
             print(json.dumps(response, indent=2))
        except Exception as ex:
             print(f"❌ Manual Request Attempt 2 FAILED: {ex}")

    await exchange.close()

if __name__ == "__main__":
    asyncio.run(main())
