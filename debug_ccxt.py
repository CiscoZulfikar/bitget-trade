import asyncio
import ccxt.async_support as ccxt
import os
from config import BITGET_API_KEY, BITGET_SECRET_KEY, BITGET_PASSPHRASE

async def test_bitget():
    print("Initializing Exchange...")
    exchange = ccxt.bitget({
        'apiKey': BITGET_API_KEY,
        'secret': BITGET_SECRET_KEY,
        'password': BITGET_PASSPHRASE,
        'options': {
            'defaultType': 'swap',
        },
        'timeout': 30000,
        'enableRateLimit': True
    })
    
    # Disable fetchCurrencies
    exchange.has['fetchCurrencies'] = False

    try:
        print("Loading markets...")
        markets = await exchange.load_markets()
        print(f"Markets loaded. Total: {len(markets)}")
        
        # Check for WIF
        target_symbol = 'WIF/USDT:USDT'
        if target_symbol not in markets:
            print(f"Warning: {target_symbol} not found directly. Searching...")
            found = [k for k in markets.keys() if 'WIF' in k]
            print(f"Found related symbols: {found}")
            if found:
                target_symbol = found[0]
            else:
                print("No WIF symbols found!")
                return

        print(f"Inspecting {target_symbol}...")
        market = markets[target_symbol]
        
        # Print Limits & Precision
        print(f"Precision: {market['precision']}")
        print(f"Limits: {market['limits']}")
        
        # Price check
        ticker = await exchange.fetch_ticker(target_symbol)
        print(f"Current Price: {ticker['last']}")
        
        # Balance check
        print("Checking Balance access...")
        balance = await exchange.fetch_balance(params={'type': 'swap'})
        usdt = balance.get('USDT', {})
        print(f"Balance check success. USDT Free: {usdt.get('free', 'N/A')}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await exchange.close()
        print("Exchange closed.")

if __name__ == "__main__":
    asyncio.run(test_bitget())
