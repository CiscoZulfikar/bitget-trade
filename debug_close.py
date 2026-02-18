
import asyncio
import ccxt.async_support as ccxt
import logging
import config
import json

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("debug_close")

async def main():
    exchange = ccxt.bitget({
        'apiKey': config.BITGET_API_KEY,
        'secret': config.BITGET_SECRET_KEY,
        'password': config.BITGET_PASSPHRASE,
        'options': {
            'defaultType': 'swap',
        }
    })

    try:
        symbol = "ETHUSDT"
        logger.info(f"Checking position for {symbol}...")
        
        # 1. Fetch Position
        positions = await exchange.fetch_positions(params={'productType': 'USDT-FUTURES'})
        target_pos = next((p for p in positions if p['symbol'] == f"{symbol}/USDT:USDT" or p['symbol'] == symbol or (p['info'].get('symbol') and symbol in p['info']['symbol'])), None)
        
        # Filter for active
        if target_pos and float(target_pos['contracts']) == 0:
             target_pos = None

        if not target_pos:
            logger.info("No open position found for ETHUSDT. Cannot test close.")
            return
        else:
            logger.info(f"Found Position: {target_pos['side']} {target_pos['contracts']}")
            
            side = target_pos['side'] # 'short'
            trade_side = 'sell' if side == 'long' else 'buy'
            
            # Close Dust Amount
            size = 0.01 # Min size might be 0.01? 
            # ETH price ~2600. 0.01 = $26. 
            # Check min amount?
            # Assuming 0.01 is valid for now.
            
            logger.info(f"Attempting to Close Dust {size} {symbol} ({side}) with tradeSide='close'...")

            # Params for Hedge Mode Close
            params = {
                'posSide': side,    # 'short'
                'tradeSide': 'close', # Explicitly close
                # 'reduceOnly': True # Optional if tradeSide is close?
            }
            
            try:
                order = await exchange.create_market_order(symbol, trade_side, size, params=params)
                logger.info(f"SUCCESS! Order Placed: {order['id']}")
            except Exception as e:
                logger.error(f"FAILED with tradeSide='close': {e}")
                
            # If that failed, try with reduceOnly=True as well?
            if 'order' not in locals():
                 logger.info("Retrying with reduceOnly=True AND tradeSide='close'...")
                 params['reduceOnly'] = True
                 try:
                    order = await exchange.create_market_order(symbol, trade_side, size, params=params)
                    logger.info(f"SUCCESS! Order Placed (Retry): {order['id']}")
                 except Exception as e:
                    logger.error(f"FAILED (Retry): {e}")


    except Exception as e:
        logger.error(f"General Error: {e}")
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(main())
