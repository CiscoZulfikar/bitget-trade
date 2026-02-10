import ccxt.async_support as ccxt
import logging
import asyncio
import aiohttp
from config import BITGET_API_KEY, BITGET_SECRET_KEY, BITGET_PASSPHRASE

logger = logging.getLogger(__name__)

class ExchangeHandler:
    def __init__(self):
        self.exchange = ccxt.bitget({
            'apiKey': BITGET_API_KEY,
            'secret': BITGET_SECRET_KEY,
            'password': BITGET_PASSPHRASE,
            'options': {
                'defaultType': 'swap',  # Futures
            },
            'timeout': 30000, # Increased timeout for heavy market loads
            'enableRateLimit': True,
            'sandboxMode': False, # Explicitly disable sandbox to prevent SUSDT-FUTURES
        })
        
        # Optimization: Disable fetchCurrencies to avoid hitting Spot API (which times out)
        # We only need Futures markets, and fetch_currencies often hits v2/spot/public/coins
        self.exchange.has['fetchCurrencies'] = False

    async def get_market_price(self, symbol):
        try:
            # Try CCXT first
            ticker = await self.exchange.fetch_ticker(symbol)
            return ticker['last']
        except Exception as ccxt_error:
            # Fallback to Raw API (Bypass load_markets)
            try:
                # Bitget V2 Mix Ticker Endpoint
                url = "https://api.bitget.com/api/v2/mix/market/ticker"
                params = {
                    "symbol": symbol, # e.g. WIFUSDT
                    "productType": "USDT-FUTURES"
                }
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=params) as resp:
                        data = await resp.json()
                        if data['code'] == '00000' and data['data']:
                            return float(data['data'][0]['last'])
                        else:
                            raise Exception(f"Raw API Error: {data}")
            except Exception as raw_error:
                logger.error(f"Price fetch failed (CCXT & Raw): {ccxt_error} | {raw_error}")
                raise raw_error

    async def get_balance(self):
        """Fetches Balance Breakdown (Free vs Equity)."""
        # CCXT 'fetch_balance' usually returns 'total' (equity) and 'free' (available)
        # Force 'swap' to avoid SUSDT error
        balance = await self.exchange.fetch_balance(params={'type': 'swap'})
        
        # Bitget Specifics:
        # 'free': Available for trade (Cross margin balance - frozen)
        # 'total': Equity (Balance + PnL)
        # Note: CCXT mapping might vary, but widely:
        # balance['USDT']['free'] = Available
        # balance['USDT']['total'] = Equity (approx) or Wallet Balance
        
        # For Bitget Futures, we want "usdtEquity" which is often mapped to 'total'
        # Let's return a detailed dict
        return {
            'free': balance.get('USDT', {}).get('free', 0.0),
            'equity': balance.get('USDT', {}).get('total', 0.0)
        }

    async def get_position(self, symbol):
        """Fetches the current open position for the symbol."""
        try:
            positions = await self.exchange.fetch_positions([symbol], params={'productType': 'USDT-FUTURES'})
            # Filter for active positions (size > 0)
            target_pos = next((p for p in positions if p['symbol'] == symbol and float(p['contracts']) > 0), None)
            return target_pos
        except Exception as e:
            logger.error(f"Error fetching position for {symbol}: {e}")
            return None

    async def get_all_positions(self):
        """Fetches ALL open positions from the exchange (for Status/Limit checks)."""
        try:
            # fetch_positions(None) or [] should return all for Bitget V2
            # Force productType
            positions = await self.exchange.fetch_positions(params={'productType': 'USDT-FUTURES'})
            
            # Filter for active positions (size > 0)
            active_pos = [p for p in positions if float(p['contracts']) > 0]
            return active_pos
        except Exception as e:
            logger.error(f"Error fetching all positions: {e}")
            return []

    async def set_leverage(self, symbol, leverage):
        try:
            # Set Leverage
            await self.exchange.set_leverage(leverage, symbol)
        except Exception as e:
            logger.warning(f"Could not set leverage: {e}")

    async def ensure_hedge_mode(self, symbol):
        try:
            # Force Hedge Mode
            # hedged=True means Hedge Mode
            await self.exchange.set_position_mode(True, symbol)
        except Exception as e:
            err_str = str(e)
            # 40789: Already in that mode
            if "40789" in err_str:
                return
            
            # 400172: Has open positions/orders (Cannot switch)
            # 43116: Generic 'condition not met' often for this too
            logger.warning(f"Set Hedge Mode Failed: {e}")
            
            # We RAISE this so the bot tells the user via Telegram
            # This explains WHY the subsequent trade would fail
            raise Exception(f"Failed to set Hedge Mode. Close all active positions/orders for {symbol} on Bitget manually and try again. ({e})")

    async def ensure_isolated_margin(self, symbol):
        try:
            # Force Isolated Margin
            # Usually set_margin_mode('isolated', symbol)
            # Check for existing mode first? CCXT might handle.
            await self.exchange.set_margin_mode('isolated', symbol)
        except Exception as e:
             err_str = str(e)
             # 40789: Already in that mode (Bitget might return this if already isolated)
             if "40789" in err_str:
                 return
             logger.warning(f"Set Isolated Margin Failed: {e}")
             # raising here might be strict, but user asked for it. 
             # If it fails (e.g. open positions), we should probably fail the trade to avoid Cross margin mishaps.
             raise Exception(f"Failed to set Isolated Margin. Close positions for {symbol} and try again. ({e})")

    async def get_active_tp_sl(self, symbol):
        """Fetches active SL and TP prices from open orders AND plan orders (Supports Partial TPs)."""
        try:
            sl_prices = []
            tp_prices = []
            
            # 1. Fetch Standard Open Orders (Limit Orders)
            try:
                orders = await self.exchange.fetch_open_orders(symbol)
                for o in orders:
                    price = None
                    if 'stopPrice' in o and o['stopPrice']: price = float(o['stopPrice'])
                    elif 'triggerPrice' in o and o['triggerPrice']: price = float(o['triggerPrice'])
                    
                    if not price: continue

                    params = o.get('info', {})
                    plan_type = params.get('planType')
                    
                    if plan_type == 'loss_plan':
                        if price not in sl_prices: sl_prices.append(price)
                    elif plan_type == 'profit_plan':
                        if price not in tp_prices: tp_prices.append(price)
            except Exception as e:
                logger.warning(f"Error fetching open orders for {symbol}: {e}")

            # 2. Fetch Plan Orders (Partial SL/TPs)
            try:
                # Use CCXT implicit method for Bitget V2 Plan Pending
                if hasattr(self.exchange, 'privateMixGetV2MixOrderOrdersPlanPending'):
                    # Sanitize Symbol for Bitget V2 (IP/USDT:USDT -> IPUSDT)
                    raw_symbol = symbol.replace("/", "").replace(":", "").split("USDT")[0] + "USDT"
                    
                    params = {
                        "symbol": raw_symbol,
                        "productType": "USDT-FUTURES",
                        "planType": "profit_loss" # Crucial!
                    }
                    # logger.info(f"Fetching Plan Orders for {raw_symbol}...")
                    response = await self.exchange.privateMixGetV2MixOrderOrdersPlanPending(params)
                    
                    if response['code'] == '00000':
                        data = response['data']['entrustedList']
                        # logger.info(f"Found {len(data)} Plan Orders for {raw_symbol}")
                        for o in data:
                            plan_type = o.get('planType')
                            price = float(o.get('triggerPrice')) if o.get('triggerPrice') else 0.0
                            
                            if price > 0:
                                if plan_type == 'loss_plan':
                                    if price not in sl_prices: sl_prices.append(price)
                                elif plan_type == 'profit_plan':
                                    if price not in tp_prices: tp_prices.append(price)
                    else:
                        logger.warning(f"Plan Order API Error for {raw_symbol}: {response}")
            except Exception as e:
                logger.warning(f"Error fetching plan orders for {symbol}: {e}")
            except Exception as e:
                logger.warning(f"Error fetching plan orders for {symbol}: {e}")

            # Sort for display
            sl_prices.sort()
            tp_prices.sort()
            
            return tp_prices, sl_prices
        except Exception as e:
            logger.warning(f"Could not fetch SL/TP for {symbol}: {e}")
            return [], []

    async def get_last_trade(self, symbol):
        """Fetches the last closed trade for a symbol to determine PnL and Exit Price."""
        try:
            # Fetch last 5 trades to find the reducing one
            # Use fetch_my_trades
            trades = await self.exchange.fetch_my_trades(symbol, limit=5)
            if trades:
                # Sort by timestamp descending
                trades.sort(key=lambda x: x['timestamp'], reverse=True)
                return trades[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching last trade for {symbol}: {e}")
            return None

    async def get_tickers(self, symbols):
        """Fetches current prices and 24h change for a list of symbols."""
        try:
            # Fetch ALL Future tickers to ensure we get the right productType data
            # Passing specific symbols to fetch_tickers with params can be flaky in CCXT/Bitget
            tickers = await self.exchange.fetch_tickers(params={'productType': 'USDT-FUTURES'})
            
            results = {}
            for s in symbols:
                # CCXT usually normalizes Bitget Futures symbols to 'BTC/USDT:USDT'
                # But our input 'symbols' are 'BTCUSDT'.
                # We need to match loose or strict.
                
                # Check direct match or normalized match
                data = None
                
                # Try finding valid ticker
                # 1. Direct match (unlikely if CCXT loaded markets)
                if s in tickers:
                    data = tickers[s]
                
                # 2. CCXT Normalized match (BTC/USDT:USDT)
                if not data:
                    # Construct CCXT format: IPUSDT -> IP/USDT:USDT
                    base = s.replace("USDT", "")
                    ccxt_sym = f"{base}/USDT:USDT"
                    if ccxt_sym in tickers:
                        data = tickers[ccxt_sym]
                        
                # 3. Raw match (if strict mode off)
                if not data:
                    # Scan keys
                    for k, v in tickers.items():
                        if k.replace("/", "").replace(":", "") == s or k.replace("/", "").split(":")[0] == s:
                             data = v
                             break
                
                if data:
                    # Rolling 24h Change
                    pct_rolling = data.get('percentage', 0.0) 
                    
                    # Daily Candle Change (UTC)
                    # Bitget raw info 'changeUtc24h' is usually decimal (e.g. -0.00708)
                    daily_change = 0.0
                    if 'info' in data and 'changeUtc24h' in data['info']:
                        try:
                            # changeUtc24h is decimal string, convert to %
                            daily_change = float(data['info']['changeUtc24h']) * 100
                        except:
                            pass
                    
                    results[s] = {
                        'last': data.get('last', 0.0),
                        'percentage': pct_rolling,      # Rolling 24h %
                        'daily_pct': daily_change       # Daily UTC Candle %
                    }
                else:
                    results[s] = {'last': 0.0, 'percentage': 0.0, 'daily_pct': 0.0}
                    
            return results
        except Exception as e:
            logger.error(f"Error fetching tickers: {e}")
            return {s: {'last': 0.0, 'percentage': 0.0, 'daily_pct': 0.0} for s in symbols}

    async def place_order(self, symbol, side, amount, leverage, sl_price=None, tp_price=None, price=None, order_type='market'):
        # 1. Ensure Hedge Mode & Isolated Margin
        await self.ensure_hedge_mode(symbol)
        await self.ensure_isolated_margin(symbol)
        
        # 2. Set leverage
        await self.set_leverage(symbol, leverage)
        
        params = {}
        # Explicitly set posSide for Hedge Mode (Bitget V2 Requirement)
        # matches side because place_order is for OPENING positions
        if side == 'buy':
            params['posSide'] = 'long' 
        else:
            params['posSide'] = 'short'
        
        # Explicitly set tradeSide to 'open' to avoid ambiguity
        params['tradeSide'] = 'open' 
        
        # Ensure marginMode is passed if needed (though account setting should prevail)
        params['marginMode'] = 'isolated' 

        logger.info(f"DEBUG: Params for {symbol} {side}: {params}")

        if sl_price:
            params['stopLoss'] = {
                'triggerPrice': sl_price,
                'type': 'market' 
            }
        if tp_price:
            params['takeProfit'] = {
                'triggerPrice': tp_price,
                'type': 'market'
            }
        
        if order_type.lower() == 'limit':
            if not price:
                logger.error("Limit order requested but no price provided.")
                return None
            logger.info(f"Placing LIMIT {side} on {symbol} at {price}")
            order = await self.exchange.create_order(symbol, 'limit', side, amount, price, params=params)
        else:
            # Market
            logger.info(f"Placing MARKET {side} on {symbol}")
            order = await self.exchange.create_order(symbol, 'market', side, amount, params=params)
            
        return order

    async def close_position(self, symbol):
        """Closes the entire position for a symbol, SYNCING with actual size first."""
        try:
            # SYNC: Fetch real position size
            target_pos = await self.get_position(symbol)
            
            if target_pos:
                side = 'sell' if target_pos['side'] == 'long' else 'buy'
                amount = float(target_pos['contracts']) # Use actual exchange size
                
                logger.info(f"Closing position {symbol}. Real size: {amount}")
                await self.exchange.create_order(symbol, 'market', side, amount)
                return True
            else:
                logger.warning(f"No active position found for {symbol} on exchange to close.")
                return False
        except Exception as e:
            logger.error(f"Close position failed: {e}")
            return False

    async def update_sl(self, symbol, order_id, new_sl):
        try:
            # 1. Get current position to know side (long/short)
            position = await self.get_position(symbol)
            if not position:
                logger.warning(f"Cannot update SL for {symbol}: No active position.")
                return False

            side = position['side'] # 'long' or 'short'
            
            # 2. Cancel Existing SL Orders (Plan Orders)
            # Use Raw API to find and cancel 'loss_plan' orders
            try:
                if hasattr(self.exchange, 'privateMixGetV2MixOrderOrdersPlanPending'):
                    # Sanitize Symbol
                    raw_symbol = symbol.replace("/", "").replace(":", "").split("USDT")[0] + "USDT"
                    params = {
                        "symbol": raw_symbol,
                        "productType": "USDT-FUTURES", 
                        "planType": "loss_plan"
                    }
                    resp = await self.exchange.privateMixGetV2MixOrderOrdersPlanPending(params)
                    
                    if resp['code'] == '00000' and 'entrustedList' in resp['data']:
                        for o in resp['data']['entrustedList']:
                             oid = o['orderId']
                             # Cancel
                             cancel_params = {
                                 "symbol": raw_symbol,
                                 "productType": "USDT-FUTURES", 
                                 "orderId": oid,
                                 "planType": "loss_plan"
                             }
                             await self.exchange.privateMixPostV2MixOrderCancelPlanOrder(cancel_params)
                             logger.info(f"Cancelled old SL order {oid} for {symbol}")
            except Exception as e:
                logger.warning(f"Error cancelling old SLs: {e}")

            # 3. Place New SL (TPSL Order for Position)
            try:
                raw_symbol = symbol.replace("/", "").replace(":", "").split("USDT")[0] + "USDT"
                req = {
                    "symbol": raw_symbol,
                    "productType": "USDT-FUTURES",
                    "marginCoin": "USDT",
                    "planType": "loss_plan",
                    "triggerPrice": str(new_sl),
                    "triggerType": "market_price",
                    "holdSide": side # long/short
                }
                res = await self.exchange.privateMixPostV2MixOrderPlaceTPSL(req)
                
                if res['code'] == '00000':
                    logger.info(f"Updated SL for {symbol} to {new_sl} (ID: {res['data']['orderId']})")
                    return True
                else:
                     logger.error(f"Failed to place new SL: {res}")
                     return False
            except Exception as e:
                logger.error(f"Failed to execute PlaceTPSL: {e}")
                return False

        except Exception as e:
            logger.error(f"Update SL failed: {e}")
            return False

    async def close(self):
        await self.exchange.close()
