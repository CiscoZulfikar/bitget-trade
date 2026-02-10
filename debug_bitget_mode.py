
import asyncio
import logging
import json
from exchange_handler import ExchangeHandler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_mode():
    exchange = ExchangeHandler()
    symbol = "BTCUSDT"
    
    try:
        print(f"--- Checking Mode for {symbol} ---")
        
        # 1. Fetch Account Info (Raw Bitget V2)
        # /api/v2/mix/account/account
        params = {
            "productType": "USDT-FUTURES",
            "symbol": symbol,
            "marginCoin": "USDT"
        }
        
        try:
            # CCXT Implicit Method for /api/v2/mix/account/account
            # Try different variations just in case
            if hasattr(exchange.exchange, 'privateMixGetV2MixAccountAccount'):
                res = await exchange.exchange.privateMixGetV2MixAccountAccount(params)
                print(f"Account Info (privateMixGetV2MixAccountAccount): {json.dumps(res, indent=2)}")
            elif hasattr(exchange.exchange, 'private_mix_get_v2_mix_account_account'):
                res = await exchange.exchange.private_mix_get_v2_mix_account_account(params)
                print(f"Account Info (private_mix_get_v2_mix_account_account): {json.dumps(res, indent=2)}")
            else:
                 print("CCXT implicit methods not found. Trying fetch_balance as proxy.")
                 
        except Exception as e:
            print(f"Raw Check Failed: {e}")

    except Exception as e:
        print(f"General Error: {e}")
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(check_mode())
