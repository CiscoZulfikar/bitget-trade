
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

    # ATTEMPT 1: User Suggested Endpoint (set-stop-order)
    print("\n--- ATTEMPT 1: set-stop-order (User Suggested) ---")
    try:
        # Endpoint: /api/v2/mix/position/set-stop-order
        # CCXT Implicit Method: privateMixPostV2MixPositionSetStopOrder
        
        params = {
            "symbol": symbol,
            "productType": productType,
            "marginCoin": marginCoin,
            "stopLoss": str(new_sl),      # Note: 'stopLoss' not 'stopLossTriggerPrice'
            "holdSide": holdSide,
            # "stopLossTriggerType": "mark_price" # Optional according to user, strict defaults might apply
        }
        
        if hasattr(exchange, 'privateMixPostV2MixPositionSetStopOrder'):
            await exchange.privateMixPostV2MixPositionSetStopOrder(params)
            print("✅ ATTEMPT 1 SUCCESS")
            await exchange.close()
            return
        else:
            print("⚠️ Method privateMixPostV2MixPositionSetStopOrder not found. Trying manual implicit call/check.")
            # Sometimes methods are not in dir() but still strictly working if constructed? 
            # But usually hasattr check is valid for CCXT implicit methods.
            
    except Exception as e:
        print(f"❌ ATTEMPT 1 FAILED: {e}")

    await exchange.close()

    await exchange.close()

if __name__ == "__main__":
    asyncio.run(main())
