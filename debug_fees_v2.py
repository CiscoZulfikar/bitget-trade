import asyncio
import logging
from exchange_handler import ExchangeHandler

# Configure logging
logging.basicConfig(level=logging.INFO)

async def check_fees():
    exchange_handler = None
    try:
        # Initialize handler (which sets fetchCurrencies=False)
        exchange_handler = ExchangeHandler()
        exchange = exchange_handler.exchange
        
        # Explicitly disable again just in case
        exchange.has['fetchCurrencies'] = False
        
        # Try to load markets but catch error
        try:
             await exchange.load_markets()
        except Exception as e:
             print(f"Load Markets Partial Error: {e}")

        symbol = "ETHUSDT" # Using the symbol from the user's report
        print(f"Fetching Position History for {symbol}...")
        
        # Try fetch_positions_history
        # Bitget V2 might call it fetch_history_orders or similar?
        # CCXT normalized: fetch_positions_history
        
        if exchange.has.get('fetchPositionsHistory'):
            try:
                # Some exchanges need params
                history = await exchange.fetch_positions_history([symbol], params={'productType': 'USDT-FUTURES'})
                # Or maybe without list?
                # history = await exchange.fetch_positions_history(symbol) 
                
                print(f"Found {len(history)} history records.")
                for h in history[:5]:
                    print(f"\n--- Position History ---")
                    print(h)
            except Exception as e:
                 print(f"fetch_positions_history failed: {e}")
                 # Try raw endpoint if CCXT fails
                 # v2/mix/position/history-position
                 print("Trying raw endpoint...")
                 params = {'productType': 'USDT-FUTURES', 'symbol': symbol, 'limit': 5}
                 res = await exchange.privateMixGetV2MixPositionHistoryPosition(params)
                 print(f"Raw Res: {res}")
        else:
            print("CCXT does not report fetchPositionsHistory support.")
            # Verify raw capability
            params = {'productType': 'USDT-FUTURES', 'symbol': symbol, 'limit': 5}
            try:
                res = await exchange.privateMixGetV2MixPositionHistoryPosition(params)
                print(f"Raw Res: {res}")
            except Exception as e:
                print(f"Raw attempt failed: {e}")

            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if exchange_handler:
            await exchange_handler.close()

if __name__ == "__main__":
    asyncio.run(check_fees())
