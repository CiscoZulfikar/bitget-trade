
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
        'options': {'defaultType': 'swap'}
    })

    # HARDCODED TEST PARAMS
    symbol = "ETHUSDT"
    productType = "USDT-FUTURES"
    marginCoin = "USDT"
    holdSide = "short" # CHANGE THIS IF YOU ARE LONG
    new_sl = "2000"

    print(f"Testing PlacePosTpsl for {symbol} ({holdSide}) -> SL: {new_sl}")
    
    # 2. Construct Payload MANUALLY (No ExchangeHandler)
    # explicitly NO 'stopLossTriggerType'
    params = {
        "symbol": symbol,
        "productType": productType,
        "marginCoin": marginCoin,
        "stopLossTriggerPrice": str(new_sl),
        "holdSide": holdSide
    }
    
    print(f"Sending Params: {params}")

    try:
        # 3. Call privateMixPostV2MixOrderPlacePosTpsl Directly
        if hasattr(exchange, 'privateMixPostV2MixOrderPlacePosTpsl'):
            resp = await exchange.privateMixPostV2MixOrderPlacePosTpsl(params)
            print("✅ SUCCESS!")
            print(resp)
        else:
            print("❌ Method privateMixPostV2MixOrderPlacePosTpsl not found on this CCXT version.")
            print("Dir check:", [x for x in dir(exchange) if 'PlacePosTpsl' in x])

    except Exception as e:
        print(f"❌ FAILURE: {e}")
        
    await exchange.close()

if __name__ == "__main__":
    asyncio.run(main())
