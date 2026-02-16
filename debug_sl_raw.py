
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
    print(f"CCXT Version: {ccxt.__version__}")
    
    exchange = ccxt.bitget({
        'apiKey': API_KEY,
        'secret': SECRET,
        'password': PASSPHRASE,
        'options': {'defaultType': 'swap'},
        'verbose': True
    })

    # HARDCODED TEST PARAMS
    symbol = "ETHUSDT"
    productType = "USDT-FUTURES"
    marginCoin = "USDT"
    holdSide = "short" # CHANGE THIS IF YOU ARE LONG
    new_sl = "2000"

    # ATTEMPT 1: PlaceTpslOrder WITH SIZE (Addressing previous error 40019)
    print("\n--- ATTEMPT 1: PlaceTpslOrder (with size) ---")
    try:
        if hasattr(exchange, 'privateMixPostV2MixOrderPlaceTpslOrder'):
            params = {
                "symbol": symbol,
                "productType": productType,
                "marginCoin": marginCoin,
                "triggerPrice": str(new_sl),
                "triggerType": "market_price",
                "planType": "loss_plan",
                "holdSide": holdSide,
                "size": "1.1" # HARDCODED SIZE from previous logs
            }
            await exchange.privateMixPostV2MixOrderPlaceTpslOrder(params)
            print("✅ ATTEMPT 1 SUCCESS")
            await exchange.close()
            return
        else:
            print("Skipping Attempt 1: Method not found")
    except Exception as e:
        print(f"❌ ATTEMPT 1 FAILED: {e}")

    # ATTEMPT 2: PlacePosTpsl with 'stopLoss' key (User Suggestion Param name)
    print("\n--- ATTEMPT 2: PlacePosTpsl (stopLoss key) ---")
    try:
        if hasattr(exchange, 'privateMixPostV2MixOrderPlacePosTpsl'):
            params = {
                "symbol": symbol,
                "productType": productType,
                "marginCoin": marginCoin,
                "stopLoss": str(new_sl),  # Trying the key 'stopLoss' instead of 'stopLossTriggerPrice'
                "holdSide": holdSide
            }
            await exchange.privateMixPostV2MixOrderPlacePosTpsl(params)
            print("✅ ATTEMPT 2 SUCCESS")
            await exchange.close()
            return
        else:
             print("Skipping Attempt 2: Method not found")
    except Exception as e:
        print(f"❌ ATTEMPT 2 FAILED: {e}")

    # ATTEMPT 3: set-stop-order (User Suggested Endpoint manually)
    print("\n--- ATTEMPT 3: Manual Request to /api/v2/mix/position/set-stop-order ---")
    try:
        params = {
            "symbol": symbol,
            "productType": productType,
            "marginCoin": marginCoin,
            "stopLoss": str(new_sl),
            "holdSide": holdSide
        }
        
        # Try finding the implicit method again or constructing it
        if hasattr(exchange, 'privateMixPostV2MixPositionSetStopOrder'):
             await exchange.privateMixPostV2MixPositionSetStopOrder(params)
             print("✅ ATTEMPT 3 SUCCESS")
        else:
             print("⚠️ ATTEMPT 3 Skipped: Method privateMixPostV2MixPositionSetStopOrder not found.")

    except Exception as e:
        print(f"❌ ATTEMPT 3 FAILED: {e}")

    await exchange.close()

if __name__ == "__main__":
    asyncio.run(main())
