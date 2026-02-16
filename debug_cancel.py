
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
    print("--- DEBUGGING PENDING ORDERS ---")
    exchange = ccxt.bitget({
        'apiKey': API_KEY,
        'secret': SECRET,
        'password': PASSPHRASE,
        'options': {'defaultType': 'swap'},
    })

    symbol = "ETHUSDT"
    productType = "USDT-FUTURES"
    
    # 1. Standard Open Orders
    print("\n[1] Checking fetch_open_orders...")
    try:
        orders = await exchange.fetch_open_orders(symbol)
        print(f"Found {len(orders)} standard orders.")
        for o in orders:
            print(f" - ID: {o['id']}, Type: {o['type']}, Side: {o['side']}, Price: {o['price']}")
    except Exception as e:
        print(f"Error fetching open orders: {e}")

    # 2. Check Plan Orders (All Types)
    print("\n[2] Checking Plan Pending Orders...")
    plan_types = ['profit_plan', 'loss_plan', 'normal_plan', 'pos_profit', 'pos_loss', 'moving_plan']
    
    for pt in plan_types:
        try:
            params = {
                "symbol": symbol,
                "productType": productType,
                "planType": pt
            }
            # Implicit method for /api/v2/mix/order/orders-plan-pending
            resp = await exchange.privateMixGetV2MixOrderOrdersPlanPending(params)
            
            if resp['code'] == '00000':
                data = resp['data']
                if data and 'entrustedList' in data and data['entrustedList']:
                    print(f"\n--- Found {pt.upper()} Orders: ---")
                    for o in data['entrustedList']:
                        print(json.dumps(o, indent=2))
                else:
                    print(f"No {pt} orders.")
            else:
                print(f"Error checking {pt}: {resp['msg']}")
                
        except Exception as e:
            print(f"Exception checking {pt}: {e}")

    await exchange.close()

if __name__ == "__main__":
    asyncio.run(main())
