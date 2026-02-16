
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
    symbols = ["ETHUSDT"]
    productTypes = ["USDT-FUTURES"]
    planTypes = ['loss_plan', 'normal_plan', 'pos_loss', 'profit_plan', 'pos_profit']
    holdSides = ['short'] # User is short

    for s in symbols:
        for p_type in productTypes:
            for plan in planTypes:
                for side in holdSides:
                    print(f"\nTrying Symbol={s}, Product={p_type}, Plan={plan}, Side={side}...")
                    try:
                        params = {
                            "symbol": s,
                            "productType": p_type,
                            "planType": plan,
                            "holdSide": side,
                            "marginCoin": "USDT" # ADDED THIS
                        }
                        resp = await exchange.privateMixGetV2MixOrderOrdersPlanPending(params)
                        
                        if resp['code'] == '00000':
                            data = resp['data'] if resp['data'] else {}
                            entrusted = data.get('entrustedList', [])
                            
                            if entrusted:
                                print(f"✅ FOUND ORDERS! Symbol={s}, Plan={plan}, Side={side}")
                                for o in entrusted:
                                    oid = o['orderId']
                                    print(f" - ID: {oid}, Type: {o['planType']}, Trigger: {o['triggerPrice']}")
                                    
                                    # SEARCH AND DESTROY
                                    print(f"   >>> ATTEMPTING TO CANCEL {oid}...")
                                    try:
                                        cancel_params = {
                                            "symbol": s,
                                            "productType": p_type,
                                            "orderId": oid,
                                            "planType": plan,
                                            "marginCoin": "USDT",
                                            "holdSide": side
                                        }
                                        c_resp = await exchange.privateMixPostV2MixOrderCancelPlanOrder(cancel_params)
                                        if c_resp['code'] == '00000':
                                            print(f"   ✅ DESTROYED {oid}")
                                        else:
                                            print(f"   ❌ FAILED TO DESTROY: {c_resp['msg']}")
                                    except Exception as ce:
                                        print(f"   ❌ EXCEPTION DURING DESTROY: {ce}")

                            else:
                                pass # Silent on clean
                        else:
                            pass # Silent on clean
                    
                    except Exception as e:
                        if "40812" in str(e):
                            pass # Common error, ignore
                        elif "40034" in str(e) or "40017" in str(e):
                             pass
                        else:
                            print(f" - EXCEPTION: {e}")

    await exchange.close()

if __name__ == "__main__":
    asyncio.run(main())
