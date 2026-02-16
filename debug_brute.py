
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
    print("--- DEBUGGING BRUTE FORCE LIST ---")
    exchange = ccxt.bitget({
        'apiKey': API_KEY,
        'secret': SECRET,
        'password': PASSPHRASE,
        'options': {'defaultType': 'swap'},
    })

    # VARIATIONS TO TRY
    symbols = ["ETHUSDT", "ETHUSDT_UMCBL"]
    productTypes = ["USDT-FUTURES", "umcbl"]
    planTypes = ['loss_plan', 'normal_plan', 'pos_loss']

    for s in symbols:
        for p_type in productTypes:
            for plan in planTypes:
                print(f"\nTrying Symbol={s}, Product={p_type}, Plan={plan}...")
                try:
                    params = {
                        "symbol": s,
                        "productType": p_type,
                        "planType": plan
                    }
                    resp = await exchange.privateMixGetV2MixOrderOrdersPlanPending(params)
                    
                    if resp['code'] == '00000':
                        data = resp['data']
                        if data and 'entrustedList' in data and data['entrustedList']:
                            print(f"✅ FOUND ORDERS! Symbol={s}, Product={p_type}, Plan={plan}")
                            for o in data['entrustedList']:
                                print(f" - ID: {o['orderId']}, Type: {o['planType']}, Trigger: {o['triggerPrice']}")
                        else:
                            print(f" - No orders (Clean response)")
                    else:
                        print(f" - Error: {resp['msg']} (Code: {resp['code']})")
                
                except Exception as e:
                    # Ignore standard errors to keep output clean, just print brief
                    if "40812" in str(e):
                        print(f" - 40812: Type not met")
                    elif "40034" in str(e) or "40017" in str(e):
                         print(f" - Param Error: {e}")
                    else:
                        print(f" - EXCEPTION: {e}")

    await exchange.close()

if __name__ == "__main__":
    asyncio.run(main())
