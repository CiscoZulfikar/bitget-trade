import asyncio
import ccxt.async_support as ccxt
import json
from config import BITGET_API_KEY, BITGET_SECRET_KEY, BITGET_PASSPHRASE

async def debug_positions_and_trades():
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
        # 1. Fetch Positions
        print("\n--- FETCHING POSITIONS ---")
        # Force productType as used in the bot
        positions = await exchange.fetch_positions(params={'productType': 'USDT-FUTURES'})
        
        print(f"Total Raw Positions Fetched: {len(positions)}")
        active_positions = [p for p in positions if float(p['contracts']) > 0]
        print(f"Active Positions (>0 contracts): {len(active_positions)}")
        
        for p in active_positions:
            print(f"\nSymbol: '{p['symbol']}'")
            print(f"ID: '{p['id']}'")
            print(f"Side: {p['side']}")
            print(f"Contracts: {p['contracts']}")
            print(f"Unrealized PnL: {p['unrealizedPnl']}")

        # 2. Fetch Recent Trades (for PnL check)
        print("\n--- FETCHING RECENT TRADES ---")
        # Try to guess a symbol if we have positions, otherwise pick a common one like BTC/USDT:USDT or WIF/USDT:USDT
        target_symbol = active_positions[0]['symbol'] if active_positions else 'BTC/USDT:USDT'
        
        # If user mentioned WIFUSDT, let's try to fetch that specifically if not in active
        if not active_positions:
            # try to find WIF
            print("No active positions. Trying to fetch trades for WIF/USDT:USDT...")
            target_symbol = 'WIF/USDT:USDT'

        print(f"Fetching trades for {target_symbol}...")
        try:
            trades = await exchange.fetch_my_trades(target_symbol, limit=5)
            print(f"Trades found: {len(trades)}")
            for t in trades:
                print(f"\nTrade ID: {t['id']}")
                print(f"Symbol: {t['symbol']}")
                print(f"Side: {t['side']}")
                print(f"Price: {t['price']}")
                print(f"Amount: {t['amount']}")
                print(f"Cost: {t['cost']}")
                print(f"Realized PnL (CCXT): {t.get('realizedPnl')}")
                print(f"Info (Raw): {json.dumps(t['info'], indent=2)}")
        except Exception as e:
            print(f"Error fetching trades for {target_symbol}: {e}")
            
    except Exception as e:
        print(f"General Error: {e}")
    finally:
        await exchange.close()
        print("\nExchange closed.")

if __name__ == "__main__":
    asyncio.run(debug_positions_and_trades())
