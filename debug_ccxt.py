import asyncio
import ccxt.async_support as ccxt
import os
from dotenv import load_dotenv

load_dotenv()

BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

async def test_bitget():
    exchange = ccxt.bitget({
        'apiKey': BITGET_API_KEY,
        'secret': BITGET_SECRET_KEY,
        'password': BITGET_PASSPHRASE,
        'options': {
            'defaultType': 'swap',
        },
        'timeout': 30000, # Testing longer timeout
        'enableRateLimit': True
    })
    
    # Disable fetchCurrencies to avoid Spot timeout
    exchange.has['fetchCurrencies'] = False

    try:
        print("Loading markets...")
        markets = await exchange.load_markets()
        print(f"Markets loaded. Total markets: {len(markets)}")
        
        # Search for WIF keys
        wif_keys = [k for k in markets.keys() if 'WIF' in k]
        print(f"Found WIF markets: {wif_keys}")
        
        # Try fetching using the unified symbol if found, else WIFUSDT
        test_symbol = 'WIF/USDT:USDT' if 'WIF/USDT:USDT' in markets else 'WIFUSDT'
        print(f"Testing fetch_ticker for: {test_symbol}")
        
        ticker = await exchange.fetch_ticker(test_symbol)
        print(f"Success! {test_symbol} Price: {ticker['last']}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(test_bitget())
