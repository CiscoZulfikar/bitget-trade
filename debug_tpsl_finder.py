
import asyncio
import os
import ccxt.async_support as ccxt
from dotenv import load_dotenv
import json

load_dotenv()
API_KEY = os.getenv("BITGET_API_KEY")
SECRET = os.getenv("BITGET_SECRET_KEY")
PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

async def main():
    print("--- DEBUGGING V2 TPSL FINDER ---")
    exchange = ccxt.bitget({
        'apiKey': API_KEY,
        'secret': SECRET,
        'password': PASSPHRASE,
        'options': {'defaultType': 'swap'},
    })

    symbol = "ETHUSDT"
    
    # TEST 1: OMIT planType
    print("\n[1] TEST: OMIT planType")
    try:
        params = {
            "symbol": symbol,
            "productType": "USDT-FUTURES",
            # "planType": OMITTED
            "marginCoin": "USDT",
            "holdSide": "short" 
        }
        resp = await exchange.privateMixGetV2MixOrderOrdersPlanPending(params)
        print(f"Resp: {resp.get('code')} - {resp.get('msg')}")
        if 'data' in resp and resp['data'] and 'entrustedList' in resp['data']:
             print(json.dumps(resp['data']['entrustedList'], indent=2))
    except Exception as e:
        print(f"Error: {e}")

    # TEST 2: LOWERCASE productType
    print("\n[2] TEST: LOWERCASE productType")
    try:
        params = {
            "symbol": symbol,
            "productType": "usdt-futures", # lower
            "planType": "loss_plan",
            "marginCoin": "USDT",
            "holdSide": "short"
        }
        resp = await exchange.privateMixGetV2MixOrderOrdersPlanPending(params)
        print(f"Resp: {resp.get('code')} - {resp.get('msg')}")
        if 'data' in resp and resp['data'] and 'entrustedList' in resp['data']:
             print(json.dumps(resp['data']['entrustedList'], indent=2))
    except Exception as e:
        print(f"Error: {e}")

    # TEST 3: UNIFIED fetch_open_orders with stop params
    print("\n[3] TEST: Unified fetch_open_orders (stop=True)")
    try:
        # Some exchanges support this
        orders = await exchange.fetch_open_orders(symbol, params={"stop": True})
        print(f"Found {len(orders)} orders.")
        for o in orders:
            print(f"ID: {o['id']}, Type: {o.get('type')}, info: {o.get('info')}")
    except Exception as e:
        print(f"Error: {e}")
        
    # TEST 4: CANCEL ALL ATTEMPT (Blind Destroy)
    # If we really can't see it, maybe we can blind-fire a cancel?
    # Usually requires ID.
    
    await exchange.close()

if __name__ == "__main__":
    asyncio.run(main())
