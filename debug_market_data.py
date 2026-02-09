import asyncio
from exchange_handler import ExchangeHandler
import logging
import json
from datetime import datetime, timezone

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_market():
    print("Initializing Exchange Handler...")
    handler = ExchangeHandler()
    
    symbol = "BTCUSDT"
    
    print(f"\n--- 1. Fetch Ticker for {symbol} ---")
    try:
        # Fetch all tickers to simulate the app's behavior
        tickers = await handler.exchange.fetch_tickers(params={'productType': 'USDT-FUTURES'})
        
        # Find BTC
        target = None
        for k, v in tickers.items():
            if k.replace("/", "").replace(":", "") == symbol or k.replace("/", "").split(":")[0] == symbol:
                target = v
                break
        
        if target:
            print("Ticker Keys:", list(target.keys()))
            print(f"Last: {target.get('last')}")
            print(f"Open: {target.get('open')} (Is this 24h rolling or daily?)")
            print(f"Percentage: {target.get('percentage')}")
            print(f"Change: {target.get('change')}")
            if 'info' in target:
                print("Raw Info:", json.dumps(target['info'], indent=2))
        else:
            print("BTC Ticker not found!")
            
    except Exception as e:
        print(f"❌ fetch_tickers failed: {e}")

    print(f"\n--- 2. Fetch Daily OHLCV for {symbol} ---")
    try:
        # Fetch 1d candle
        # CCXT symbol format might be needed: BTC/USDT:USDT
        ccxt_symbol = "BTC/USDT:USDT" 
        ohlcv = await handler.exchange.fetch_ohlcv(ccxt_symbol, timeframe='1d', limit=1)
        
        if ohlcv:
            # [timestamp, open, high, low, close, volume]
            candle = ohlcv[0]
            ts = candle[0]
            open_price = candle[1]
            close_price = candle[4]
            current_date = datetime.fromtimestamp(ts/1000, timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            
            print(f"Candle Time: {current_date}")
            print(f"Open: {open_price}")
            print(f"Close (Current): {close_price}")
            
            # Calculate Daily %
            change = ((close_price - open_price) / open_price) * 100
            print(f"Calculated Daily %: {change:.2f}%")
        else:
            print("No OHLCV data returned.")

    except Exception as e:
        print(f"❌ fetch_ohlcv failed: {e}")

    await handler.close()

if __name__ == "__main__":
    asyncio.run(debug_market())
