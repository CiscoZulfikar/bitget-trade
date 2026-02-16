import asyncio
import logging
from exchange_handler import ExchangeHandler

# Configure logging
logging.basicConfig(level=logging.INFO)

async def check_fees():
    exchange = None
    try:
        exchange = ExchangeHandler()
        # Load markets first (important for bitget)
        await exchange.exchange.load_markets()
        
        symbol = "ETHUSDT" # Using the symbol from the user's report
        print(f"Fetching trades for {symbol}...")
        
        # Fetch last 5 trades
        trades = await exchange.exchange.fetch_my_trades(symbol, limit=5)
        
        if trades:
            for i, t in enumerate(trades):
                print(f"\n--- Trade {i} ---")
                print(f"Timestamp: {t['timestamp']} ({t['datetime']})")
                print(f"Side: {t['side']}")
                print(f"Price: {t['price']}")
                print(f"Amount: {t['amount']}")
                print(f"Cost: {t['cost']}")
                print(f"Fee: {t.get('fee')}")
                print(f"Info (Raw): {t['info']}")
                
                # Check realized PnL in info
                if 'info' in t:
                    print(f"Realized PnL (info): {t['info'].get('profit') or t['info'].get('cRealizedPL') or t['info'].get('closedStat')}")
        else:
            print("No trades found.")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if exchange:
            await exchange.exchange.close()

if __name__ == "__main__":
    asyncio.run(check_fees())
