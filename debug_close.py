
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
            logger.info("No open position found for ETHUSDT. Attempting to OPEN a small dust position to test closing? (SKIPPING FOR NOW)")
            # return
        else:
            logger.info(f"Found Position: {target_pos['side']} {target_pos['contracts']}")
            logger.info(f"Raw Info: {json.dumps(target_pos['info'], indent=2)}")

            # Check Margin Mode
            # marginMode usually in info
            logger.info(f"Margin Mode: {target_pos['info'].get('marginMode')}")
            logger.info(f"Hold Mode: {target_pos['info'].get('holdMode')}") # double_hold (Hedge) or single_hold (One-Way)

            side = target_pos['side']
            size = float(target_pos['contracts'])
            trade_side = 'sell' if side == 'long' else 'buy'

            # 2. Test Close - One Way Strict
            logger.info("Tentative Close - Test 1: Empty Params (One-Way Standard)")
            try:
                # We won't actually execute if we can validly validate, but create_order validates.
                # Let's try to place a reduceOnly order without posSide
                params = {'reduceOnly': True}
                # order = await exchange.create_market_order(symbol, trade_side, size, params=params)
                # logger.info(f"Test 1 Success: {order['id']}")
            except Exception as e:
                logger.error(f"Test 1 Failed: {e}")

    except Exception as e:
        logger.error(f"General Error: {e}")
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(main())
