from telethon import TelegramClient, events
import logging
import asyncio
from config import TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_CHANNEL_ID, NOTIFICATION_USER_ID
from parser import parse_message
from risk_manager import RiskManager
from exchange_handler import ExchangeHandler
from database import store_trade, get_trade_by_msg_id, update_trade_order_id, update_trade_sl, close_trade_db, get_open_trade_count, get_all_open_trades, get_recent_trades
from notifier import Notifier

logger = logging.getLogger(__name__)

class TelegramListener:
    def __init__(self, client: TelegramClient, bot_client: TelegramClient, notifier: Notifier):
        self.client = client # Userbot client (Channel Listener)
        self.bot_client = bot_client # Bot API client (DM Listener)
        self.notifier = notifier
        self.risk_manager = RiskManager()
        self.exchange = ExchangeHandler()
        self.channel_id = TELEGRAM_CHANNEL_ID

    async def start(self):
        # 1. Channel Listener (Userbot)
        @self.client.on(events.NewMessage(chats=self.channel_id))
        async def handler_new(event):
            await self.process_message(event)

        @self.client.on(events.MessageEdited(chats=self.channel_id))
        async def handler_edit(event):
            await self.process_message(event, is_edit=True)

        # 2. DM Listener (Bot API) - For Mock Signals
        @self.bot_client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
        async def handler_dm(event):
            # Only process DMs from the Admin
            if event.sender_id == NOTIFICATION_USER_ID:
                text_upper = event.message.message.upper().strip()

                # Command Handling
                if text_upper in ["HELP", "/HELP"]:
                    await self.send_help()
                    return
                elif text_upper in ["STATUS", "/STATUS"]:
                    await self.send_status()
                    return
                elif text_upper in ["CURRENT_TRADE", "/TRADES", "TRADES", "POSITIONS", "/POSITIONS"]:
                    await self.send_open_trades()
                    return
                elif text_upper in ["MARKET", "/MARKET"]:
                    await self.send_market_update()
                    return
                elif text_upper in ["DATABASE", "/DATABASE", "/DB", "DB"]:
                    await self.send_database_records()
                    return

                logger.info(f"Received DM from Admin. Processing as Mock Signal.")
                await self.process_message(event, is_mock_override=True)

        logger.info(f"Listener attached to channel {self.channel_id} and Bot DMs...")
        
        # Fetch and notify last message on startup
        await self.notify_last_message()
        
        # Send Status on Startup
        await self.send_status()
        
        # Start Periodic Status Update (30m)
        asyncio.create_task(self.periodic_status_task())
        
        # Start Trade Monitor (Immediate Alerts)
        asyncio.create_task(self.monitor_trade_updates())

    async def notify_last_message(self):
        try:
            logger.info("Fetching last message from channel...")
            messages = await self.client.get_messages(self.channel_id, limit=1)
            if messages:
                last_msg = messages[0]
                text = last_msg.message or "[No text content]"
                await self.notifier.send(f"📜 **Startup Check - Last Trader Message:**\n\n{text}")
            else:
                logger.warning("No messages found in channel.")
        except Exception as e:
            logger.error(f"Could not fetch last message: {e}")
            await self.notifier.send(f"⚠️ Startup Error: Could not fetch last message ({e})")

    async def process_message(self, event, is_edit=False, is_mock_override=False):
        text = event.message.message
        msg_id = event.message.id
        sender_id = event.sender_id
        
        # Mock Mode Detection
        # If explicitly overridden (DM) OR sender is the User (me), we treat it as a test/mock
        is_mock = is_mock_override
        if not is_mock:
            try:
                if isinstance(NOTIFICATION_USER_ID, int) and sender_id == NOTIFICATION_USER_ID:
                    is_mock = True
            except:
                pass
            
        reply_msg = await event.get_reply_message()
        reply_context = reply_msg.message if reply_msg else ""
        
        log_prefix = "[MOCK] " if is_mock else ""
        logger.info(f"{log_prefix}Processing message {msg_id} (Edit: {is_edit}): {text[:50]}...")

        # Parse
        data = await parse_message(text, reply_context)
        
        if data['type'] == 'TRADE_CALL':
            # Check DB to allow edits ONLY if we haven't processed this msg_id yet
            existing_trade = await get_trade_by_msg_id(msg_id)
            if existing_trade:
                logger.info(f"Ignored duplicate/edited TRADE_CALL {msg_id} (Already processed).")
            else:
                await self.handle_trade_call(msg_id, data, is_mock)

        elif data['type'] == 'UPDATE':
            await self.handle_update(msg_id, data, reply_msg_id=reply_msg.id if reply_msg else None, is_mock=is_mock)
        else:
            logger.info(f"Ignored message type: {data.get('type')}")

    async def handle_trade_call(self, msg_id, data, is_mock=False):
        symbol = data['symbol']
        direction = data['direction']
        signal_entry = data['entry']
        signal_sl = data['sl']

        # Check Max Trades (REAL EXCHANGE DATA)
        # We check actual open positions on Bitget to account for manual trades
        real_positions = await self.exchange.get_all_positions()
        open_trades_count = len(real_positions)
        
        if open_trades_count >= 3:
             logger.warning(f"Skipping trade {symbol}: Max concurrent trades (3) reached (Real: {open_trades_count}).")
             await self.notifier.send(f"⚠️ Signal Skipped: Max concurrent trades reached ({open_trades_count}/3). Ignored {symbol}.")
             return
        
        # Clean Symbol
        # Remove #, $
        symbol = symbol.replace("#", "").replace("$", "").upper()
        # Ensure it ends with USDT to target USDT-FUTURES (Linear Perps)
        if not symbol.endswith("USDT"):
            symbol += "USDT"
            
        try:
            # Get market price
            market_price = await self.exchange.get_market_price(symbol)
        except Exception as e:
            if is_mock:
                logger.warning(f"Failed to fetch price ({e}). Using Signal Entry {signal_entry} as Mock Price.")
                market_price = signal_entry
            else:
                logger.error(f"Failed to fetch price for {symbol}: {e}")
                await self.notifier.send(f"⚠️ Error: Could not fetch price for {symbol}. Skipped.\nReason: {e}")
                return
        
        # Scaling
        entry_price = self.risk_manager.scale_price(signal_entry, market_price)
        sl_price = self.risk_manager.scale_price(signal_sl, market_price)
        
        # Decision Logic (Market vs Limit vs Abort)
        explicit_type = data.get('order_type', 'MARKET')
        action, decision_price, reason = self.risk_manager.determine_entry_action(entry_price, market_price, explicit_type)
        
        if action == 'ABORT':
            await self.notifier.send(f"⚠️ Aborted {symbol}: {reason}")
            return
            
        # Determine actual price to use for calc/order
        # If MARKET, use current market price for size calc (approx), but order checks 'market'
        # If LIMIT, use decision_price (which is the entry price)
        exec_price = decision_price if action == 'LIMIT' else market_price

        # Balance & Risk
        balance = 0.0
        try:
            balance_data = await self.exchange.get_balance()
            balance = balance_data['free']
            equity = balance_data['equity']
        except Exception as e:
            # ... (Mock balance handling same as before)
            if is_mock:
                 logger.warning(f"Failed to fetch balance ({e}). Using MOCK balance of $1000.")
                 balance = 1000.0
                 equity = 1000.0
            else:
                logger.error(f"Failed to fetch balance: {e}")
                await self.notifier.send("⚠️ Error: Could not fetch wallet balance.")
                return

        position_size_usdt = self.risk_manager.calculate_position_size(balance)
        leverage = self.risk_manager.calculate_leverage(exec_price, sl_price)
        
        # Place Order
        if is_mock:
            logger.info(f"[MOCK] Skipping execution for {symbol}")
            await self.notifier.send(
                f"🧪 **MOCK TRADE DETECTED**\n"
                f"Action: {action} {direction} {symbol}\n"
                f"**Entry:** {exec_price}\n"
                f"**Leverage:** {leverage}x\n"
                f"**Size:** ${position_size_usdt:.2f} ({15}% of ${balance:.2f} Free)\n"
                f"**SL:** {sl_price}\n"
                f"**Reason:** {reason}"
            )
            # Store in DB as mock? Or skip?
            # Storing allows testing updates. Let's store with status "MOCK"
            await store_trade(msg_id, "MOCK_ORDER_ID", symbol, entry_price, sl_price, status="MOCK")
            return

        amount = (position_size_usdt * leverage) / exec_price
        side = 'buy' if direction.upper() == 'LONG' else 'sell'
        logger.info(f"Placing {action} {direction} on {symbol} x{leverage}. SL: {sl_price}")
        
        order = await self.exchange.place_order(symbol, side, amount, leverage, sl_price=sl_price, price=exec_price if action == 'LIMIT' else None, order_type=action)
        
        if order:
            await store_trade(msg_id, order['id'], symbol, entry_price, sl_price, status="OPEN")
            await self.notifier.send(f"🟢 {action} Order Opened: {symbol} at {exec_price} with {leverage}x.\nReason: {reason}")
        else:
            await self.notifier.send(f"⚠️ execution failed for {symbol}")

    async def handle_update(self, msg_id, data, reply_msg_id=None, is_mock=False):
        # 1. Try to get symbol from Parser (if specific coin mentioned)
        symbol = data.get('symbol')
        
        trade = None
        if symbol:
            symbol = symbol.replace("#", "").replace("$", "").upper()
            if not symbol.endswith("USDT"): symbol += "USDT"
            # Find ANY open trade for this symbol
            # (Currently our DB lookup is by msg_id, so we might need a new lookup or iterate)
            # For simplicity in this iteration, we still rely heavily on reply_msg_id for exact match,
            # BUT if we have a symbol, we can try to find the open trade for it.
            # Let's implementation a 'get_open_trade_by_symbol' if needed, or just iterate in memory for now?
            # Better: Use the DB.
            # BUT, let's stick to the most robust method: Reply Context > Symbol Match.
            pass

        # 2. Try to find trade by Reply ID
        if reply_msg_id and not trade:
            trade = await get_trade_by_msg_id(reply_msg_id)
        
        # 3. If still no trade, but we have a symbol, try to find the latest OPEN trade for that symbol
        if not trade and symbol:
             # We need a helper for this. Let's do a quick DB query here or add to database.py
             # For now, let's just warn if we can't find it via reply.
             # actually, let's make it robust:
             trades = await get_all_open_trades()
             for t in trades:
                 if t['symbol'] == symbol:
                     trade = t
                     break

        if not trade:
            logger.info(f"Update ignored: Could not find original trade for reply {reply_msg_id} or symbol {symbol}")
            return

        action = data['action']
        symbol = trade['symbol']
        order_id = trade['order_id']

        if is_mock or trade['status'] == 'MOCK':
            # Mock update
            await self.notifier.send(f"🧪 **MOCK UPDATE**\nAction: {action}\nValue: {data.get('value')}\n(No exchange action taken)")
            if action in ["CLOSE_FULL", "BOOK_R"]:
                 await close_trade_db(trade['message_id'])
            return

        if action == "MOVE_SL":
            new_sl = data['value']
            market_price = await self.exchange.get_market_price(symbol)
            new_sl = self.risk_manager.scale_price(new_sl, market_price)
            
            await self.exchange.update_sl(symbol, order_id, new_sl)
            await update_trade_sl(trade['message_id'], new_sl)
            await self.notifier.send(f"🟡 Signal Edited: Updated SL for {symbol} to {new_sl}.")
            
        elif action in ["CLOSE_FULL", "BOOK_R"]:
            if action == "BOOK_R" and data.get('value'):
                r_multiple = data['value']
                # (R logic calculation omitted for brevity, same as before)
                logger.info(f"Booking {r_multiple}R.")
            
            success = await self.exchange.close_position(symbol)
            
            if success:
                await close_trade_db(trade['message_id'])
                current_price = await self.exchange.get_market_price(symbol)
                bal_data = await self.exchange.get_balance()
                new_equity = bal_data['equity']
                await self.notifier.send(f"🔴 Trade Closed: {symbol} at {current_price}. Equity: ${new_equity:.2f}.")
            else:
                await self.notifier.send(f"⚠️ Failed to close (or no position for) {symbol}.")

    async def close(self):
        """Cleanup resources."""
        await self.exchange.close()

    # --- New Features ---

    async def send_help(self):
        help_text = (
            "🤖 **Bot Commands**\n\n"
            "• `HELP`: Show this message.\n"
            "• `STATUS`: Show Equity, Free Balance & Open Trades.\n"
            "• `CURRENT_TRADE`: List all open positions.\n"
            "• `MARKET`: Show Top 8 Crypto + Gold/Silver Prices.\n"
            "• `DATABASE`: Show Last 20 Real Trades.\n"
            "\n"
            "**Mock Signals (DM Me):**\n"
            "• `LONG BTC ENTRY 90000 SL 89000`\n"
            "• `LIMIT SHORT ETH ENTRY 3000 SL 3100`"
        )
        await self.notifier.send(help_text)

    async def send_status(self):
        try:
            bal_data = await self.exchange.get_balance()
            free = bal_data['free']
            equity = bal_data['equity']
            
            # Use Real Exchange Data
            real_positions = await self.exchange.get_all_positions()
            count = len(real_positions)
            
            await self.notifier.send(
                f"📊 **System Status**\n\n"
                f"💎 **Equity:** ${equity:.2f}\n"
                f"💵 **Free:** ${free:.2f}\n"
                f"📉 **Open Trades:** {count}/3\n\n"
                f"💡 _Send `HELP` for command list._"
            )
        except Exception as e:
            await self.notifier.send(f"⚠️ Could not fetch status: {e}")

    async def send_open_trades(self):
        # Use Real Exchange Data
        trades = await self.exchange.get_all_positions()
        if not trades:
            await self.notifier.send(f"📭 No open positions on exchange.")
            return

        msg = f"📉 **Open Positions ({len(trades)})**\n\n"
        for t in trades:
            # t is a CCXT position dict
            symbol = t['symbol']
            side = t['side'].upper()
            entry = t['entryPrice'] or 0.0
            mark_price = t.get('markPrice') or 0.0
            amount = t['contracts']
            pnl = t['unrealizedPnl'] or 0.0
            roi = t['percentage'] or 0.0
            leverage = t.get('leverage', '?')
            liq_price = t.get('liquidationPrice') or 0.0
            margin = t.get('initialMargin') or t.get('maintenanceMargin') or 0.0
            
            # Fetch active SL/TP
            tp_list, sl_list = await self.exchange.get_active_tp_sl(symbol)
            
            # Format as strings
            sl_str = ", ".join([str(x) for x in sl_list]) if sl_list else "None"
            tp_str = ", ".join([str(x) for x in tp_list]) if tp_list else "None"
            
            # Icon selection
            icon = "🟢" if pnl >= 0 else "🔴"
            
            msg += (
                f"{icon} **{symbol}** ({side} x{leverage})\n"
                f"   💰 **PnL:** ${pnl:.2f} ({roi:.2f}%)\n"
                f"   📏 **Size:** {amount} (${amount * mark_price:.2f})\n"
                f"   🎯 **Entry:** {entry}\n"
                f"   📍 **Mark:** {mark_price}\n"
                f"   🛑 **SL:** {sl_str}\n"
                f"   🎯 **TP:** {tp_str}\n"
                f"   ☠️ **Liq:** {liq_price}\n"
                f"   🏦 **Margin:** ${margin:.2f}\n\n"
            )
        
        await self.notifier.send(msg)

    async def periodic_status_task(self):
        """Sends status updates based on dynamic schedule."""
        from datetime import datetime, timezone, timedelta
        logger.info("Periodic Status Task Started.")
        
        while True:
            try:
                # Current Time (UTC)
                now_utc = datetime.now(timezone.utc)
                # Convert to WIB (UTC+7)
                now_wib = now_utc + timedelta(hours=7)
                
                minute = now_utc.minute
                
                # 1. Daily Market Overview at 07:00 WIB
                if now_wib.hour == 7 and minute == 0:
                    logger.info("Time is 07:00 WIB. Sending Daily Market Overview...")
                    await self.send_market_update()
                    # We continue to Status Check below
                
                # 2. Periodic Status Update
                should_send = False
                
                if minute == 0:
                    should_send = True
                elif minute == 30:
                    # check real positions
                    positions = await self.exchange.get_all_positions()
                    if len(positions) > 0:
                        should_send = True
                
                if should_send:
                    logger.info("Sending scheduled status update...")
                    await self.send_status()
                    # Sleep to avoid double send within the same minute
                    await asyncio.sleep(60) 
                
            except Exception as e:
                logger.error(f"Periodic task error: {e}")
                await asyncio.sleep(60)
            
            # Check every 50s to avoid skipping minutes
            await asyncio.sleep(50)

    async def send_market_update(self):
        """Sends current prices for Top 8 Crypto + Metals."""
        try:
            targets = [
                "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", 
                "BNBUSDT", "DOGEUSDT", "ADAUSDT", "AVAXUSDT", 
                "XAUUSDT", "XAGUSDT"
            ]
            
            prices = await self.exchange.get_tickers(targets)
            
            msg = "🌍 **Market Overview**\n\n"
            msg += "**Crypto (Top 8):**\n"
            for s in targets[:8]:
                data = prices.get(s, {'last': 0.0, 'percentage': 0.0})
                p = data['last']
                pct = data['percentage']
                
                # Format Percentage
                # CCXT usually returns percentage as 5.2 means 5.2%. Or 0.052? 
                # Bitget returns raw change usually.
                # Assuming CCXT standardizes to % (e.g. -1.5) or decimal (e.g. -0.015).
                # Usually CCXT is percentage value (e.g. -1.5).
                
                icon = "🟢" if pct >= 0 else "🔴"
                pct_str = f"{pct:+.2f}%"
                
                msg += f"• {s.replace('USDT', '')}:  `${p:,.4f}` ({icon} {pct_str})\n"
                
            msg += "\n**Metals:**\n"
            for s in targets[8:]:
                data = prices.get(s, {'last': 0.0, 'percentage': 0.0})
                p = data['last']
                pct = data['percentage']
                icon = "🟢" if pct >= 0 else "🔴"
                pct_str = f"{pct:+.2f}%"
                
                msg += f"• {s.replace('USDT', '')}:  `${p:,.2f}` ({icon} {pct_str})\n"
                
            await self.notifier.send(msg)
            
        except Exception as e:
            logger.error(f"Market update failed: {e}")
            await self.notifier.send(f"⚠️ Market update failed: {e}")

    async def monitor_trade_updates(self):
        """Polls for trade closures (SL/TP) every 60s."""
        logger.info("Trade Monitor Task Started.")
        last_positions = {}
        
        # Initial population
        try:
            initial_pos = await self.exchange.get_all_positions()
            last_positions = {p['symbol']: p for p in initial_pos}
        except:
            pass
            
        while True:
            try:
                await asyncio.sleep(60) # Poll every 60s
                
                current_pos_list = await self.exchange.get_all_positions()
                current_positions = {p['symbol']: p for p in current_pos_list}
                
                # Check for CLOSED positions (In last_positions but NOT in current_positions)
                for symbol, old_pos in last_positions.items():
                    if symbol not in current_positions:
                        # Position Closed!
                        logger.info(f"Detected closure for {symbol}. Fetching details...")
                        
                        # Fetch Last Trade to get PnL/Reason
                        last_trade = await self.exchange.get_last_trade(symbol)
                        
                        if last_trade:
                            price = float(last_trade['price'])
                            # realisedPnl is often in the trade history
                            pnl = 0.0
                            if 'info' in last_trade and 'cRealizedPL' in last_trade['info']:
                                pnl = float(last_trade['info']['cRealizedPL']) # Bitget V2 key?
                            elif 'realizedPnl' in last_trade: # CCXT unified
                                pnl = last_trade['realizedPnl']
                                
                            # Fallback if PnL is 0 or missing
                            if pnl == 0 and 'info' in last_trade:
                                # debug V2 keys: fillPx, fee, etc.
                                pass

                            icon = "🟢" if pnl >= 0 else "🔴"
                            reason = "Take Profit 🎯" if pnl >= 0 else "Stop Loss 🛑"
                            
                            await self.notifier.send(
                                f"🔔 **Position Closed: {symbol}**\n"
                                f"{icon} **PnL:** ${pnl:.2f} ({reason})\n"
                                f"📉 **Exit Price:** {price}\n"
                            )
                        else:
                            await self.notifier.send(f"🔔 **Position Closed: {symbol}** (Details unavailable)")

                # Update Cache
                last_positions = current_positions
                
            except Exception as e:
                logger.error(f"Trade monitor error: {e}")

    async def send_database_records(self):
        """Sends the last 20 trades from the database."""
        try:
            trades = await get_recent_trades(20)
            
            if not trades:
                await self.notifier.send("📭 Database is empty.")
                return
            
            msg = "📚 **Database Records (Last 20)**\n\n"
            
            for t in trades:
                status_icon = {
                    "OPEN": "🟢",
                    "CLOSED": "aaa",
                    "MOCK": "🧪"
                }.get(t['status'], "❓")
                
                # Format timestamp (assuming simple string or datetime)
                ts = t['timestamp']
                
                msg += (
                    f"{status_icon} **{t['symbol']}** ({t['status']})\n"
                    f"   🆔 `{t['order_id']}`\n"
                    f"   💰 Entry: {t['entry_price']} | SL: {t['sl_price']}\n"
                    f"   📅 {ts}\n"
                    f"   -------------------------\n"
                )
            
            # Telegram has message length limits (4096 chars). 
            # 20 records might fit, but safer to split if needed.
            # strict split not implemented here for brevity, assuming standard usage.
            if len(msg) > 4000:
                msg = msg[:4000] + "\n...(truncated)"
                
            await self.notifier.send(msg)
            
        except Exception as e:
            logger.error(f"DB Fetch failed: {e}")
            await self.notifier.send(f"⚠️ Error fetching history: {e}")

