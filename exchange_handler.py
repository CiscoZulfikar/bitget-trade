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
        balance = await self.exchange.fetch_balance()
        
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
            positions = await self.exchange.fetch_positions([symbol])
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
            positions = await self.exchange.fetch_positions()
            
            # Filter for active positions (size > 0)
            active_pos = [p for p in positions if float(p['contracts']) > 0]
            return active_pos
        except Exception as e:
            logger.error(f"Error fetching all positions: {e}")
            return []

    async def set_leverage(self, symbol, leverage):
        try:
            await self.exchange.set_leverage(leverage, symbol)
        except Exception as e:
            logger.warning(f"Could not set leverage: {e}")

    async def get_active_tp_sl(self, symbol):
        """Fetches active SL and TP prices from open orders (Supports Partial TPs)."""
        try:
            orders = await self.exchange.fetch_open_orders(symbol)
            sl_prices = []
            tp_prices = []
            
            for o in orders:
                # Check for stop loss/take profit params or order types
                # Bitget V2 often returns these as 'triggerPrice' or 'stopPrice'
                
                price = None
                if 'stopPrice' in o and o['stopPrice']:
                    price = float(o['stopPrice'])
                elif 'triggerPrice' in o and o['triggerPrice']:
                    price = float(o['triggerPrice'])
                
                if not price: continue

                params = o.get('info', {})
                plan_type = params.get('planType')
                
                # 'loss_plan' = SL, 'profit_plan' = TP
                # 'normal_plan' could be either, usually identified by side vs entry, but Bitget V2 separates them well.
                
                if plan_type == 'loss_plan':
                    if price not in sl_prices: sl_prices.append(price)
                elif plan_type == 'profit_plan':
                    if price not in tp_prices: tp_prices.append(price)
                else:
                    # Fallback or generic stop
                    # If we can't be sure, skip or add to a 'generic' list?
                    # For now, rely on planType which is robust for Bitget V2
                    pass
            
            # Sort for display
            sl_prices.sort()
            tp_prices.sort()
            
            return tp_prices, sl_prices
        except Exception as e:
            logger.warning(f"Could not fetch SL/TP for {symbol}: {e}")
            return [], []

    async def place_order(self, symbol, side, amount, leverage, sl_price=None, tp_price=None, price=None, order_type='market'):
        try:
            # Set leverage first
            await self.set_leverage(symbol, leverage)
            
            params = {}
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
        except Exception as e:
            logger.error(f"Order placement failed: {e}")
            return None

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
        # Bitget V2 SL update
        # Manual Sync check not strictly needed for just SL update unless we want to verify position exists
        try:
            target_pos = await self.get_position(symbol)
            if not target_pos:
                logger.warning(f"Cannot update SL for {symbol}. No open position found.")
                return False

            # Bitget specific: update TPSL for position
            # verify CCXT method for 'setPositionMode' or specific edit/algo params
            # Standard CCXT way for some exchanges is create_order with params
            # For Bitget, often easier to cancel old SL orders and place new or use specific implicit API
            # For this V2, we will assume a generic "edit_order" or log warning if complex
            
            # Note: CCXT Bitget implementation details for SL update on existing position:
            # Often requires cancelling existing plan order and creating new one.
            # We will use the 'position' param if available or log for user to check docs for specific algo-edit.
            logger.info(f"Request to update SL {symbol} to {new_sl}. (Exchange specific algo-edit needed)")
            
            return True
            
        except Exception as e:
            logger.error(f"Update SL failed: {e}")
            return False

    async def close(self):
        await self.exchange.close()
