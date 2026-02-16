
import asyncio
import os
import ccxt.async_support as ccxt
from dotenv import load_dotenv

# 1. Load params
load_dotenv()
API_KEY = os.getenv("BITGET_API_KEY")
SECRET = os.getenv("BITGET_SECRET_KEY")
PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

async def main():
    print("Initializing Raw Bitget V2...")
    exchange = ccxt.bitget({
        'apiKey': API_KEY,
        'secret': SECRET,
        'password': PASSPHRASE,
        'options': {'defaultType': 'swap'},
        'verbose': True
    })

    symbol = "ETHUSDT"
    productType = "USDT-FUTURES"
    marginCoin = "USDT"
    holdSide = "short" 
    new_sl = "2000"

    # ATTEMPT 1: PlacePosTpsl (Current Best Guess)
    print("\n--- ATTEMPT 1: PlacePosTpsl with plain params ---")
    try:
        params = {
            "symbol": symbol,
            "productType": productType,
            "marginCoin": marginCoin,
            "stopLossTriggerPrice": str(new_sl),
            "holdSide": holdSide
        }
        await exchange.privateMixPostV2MixOrderPlacePosTpsl(params)
        print("✅ ATTEMPT 1 SUCCESS")
        await exchange.close()
        return
    except Exception as e:
        print(f"❌ ATTEMPT 1 FAILED: {e}")

    # ATTEMPT 2: PlaceTpslOrder (Alternative Endpoint)
    print("\n--- ATTEMPT 2: PlaceTpslOrder ---")
    try:
        if hasattr(exchange, 'privateMixPostV2MixOrderPlaceTpslOrder'):
            params = {
                "symbol": symbol,
                "productType": productType,
                "marginCoin": marginCoin,
                "stopLossTriggerPrice": str(new_sl),
                "stopLossTriggerType": "market_price", # Try sending it here
                "holdSide": holdSide,
                "planType": "loss_plan"
            }
            await exchange.privateMixPostV2MixOrderPlaceTpslOrder(params)
            print("✅ ATTEMPT 2 SUCCESS")
            await exchange.close()
            return
        else:
            print("Skipping Attempt 2: Method not found")
    except Exception as e:
        print(f"❌ ATTEMPT 2 FAILED: {e}")

    # ATTEMPT 3: V1 PlaceTPSL (Legacy Fallback)
    print("\n--- ATTEMPT 3: V1 PlaceTPSL ---")
    try:
         if hasattr(exchange, 'privateMixPostMixV1PlanPlaceTPSL'):
            params = {
                "symbol": symbol,
                "marginCoin": marginCoin,
                "slPrice": str(new_sl),
                "holdSide": holdSide
            }
            await exchange.privateMixPostMixV1PlanPlaceTPSL(params)
            print("✅ ATTEMPT 3 SUCCESS")
            await exchange.close()
            return
    except Exception as e:
        print(f"❌ ATTEMPT 3 FAILED: {e}")

    await exchange.close()

if __name__ == "__main__":
    asyncio.run(main())
