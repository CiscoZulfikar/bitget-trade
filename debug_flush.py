
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
    print("--- DEBUGGING SYSTEM FLUSH (V1) ---")
    print("V2 Listing is failing (40812). We must cleaning the pipes with V1.")
    
    exchange = ccxt.bitget({
        'apiKey': API_KEY,
        'secret': SECRET,
        'password': PASSPHRASE,
        'options': {'defaultType': 'swap'},
    })

    symbol = "ETHUSDT"
    
    # Plan Types to Flush
    plans = ['loss_plan', 'profit_plan', 'pos_loss', 'pos_profit', 'normal_plan', 'moving_plan']
    
    for plan in plans:
        print(f"\n>>> FLUSHING {plan} params...")
        try:
            # V1 Endpoint: /api/mix/v1/plan/cancelSymbolPlan
            # Params: symbol, planType
            params = {
                "symbol": symbol,
                "planType": plan,
                "marginCoin": "USDT" # Just in case
            }
            
            if hasattr(exchange, 'privateMixPostMixV1PlanCancelSymbolPlan'):
                resp = await exchange.privateMixPostMixV1PlanCancelSymbolPlan(params)
                print(f"Response: {resp}")
                if resp.get('code') == '00000':
                    print(f"✅ V1 FLUSH SUCCESS for {plan}")
                else:
                    print(f"❌ V1 FLUSH FAILED: {resp.get('msg')}")
            else:
                print("❌ Method privateMixPostMixV1PlanCancelSymbolPlan not found.")

        except Exception as e:
            print(f"Exception flushing {plan}: {e}")

    await exchange.close()

if __name__ == "__main__":
    asyncio.run(main())
