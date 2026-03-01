from telethon import TelegramClient, events
import logging
import asyncio
from config import TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_CHANNEL_ID, NOTIFICATION_USER_ID
from parser import parse_message
from risk_manager import RiskManager
from exchange_handler import ExchangeHandler
from database import store_trade, get_trade_by_msg_id, update_trade_order_id, update_trade_sl, close_trade_db, get_open_trade_count, get_all_open_trades, get_recent_trades, reserve_trade, update_trade_full, get_stats_report, get_monthly_stats, clear_all_trades, update_trade_entry, update_trade_tp
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
                elif text_upper.startswith("PERFORMANCE") or text_upper.startswith("/PERFORMANCE") or text_upper.startswith("STATS") or text_upper.startswith("/STATS"):
                    await self.send_performance_stats(event.message.message)
                    return
                elif text_upper in ["DATABASE", "/DATABASE", "/DB", "DB"]:
                    await self.send_database_records()
                    return
                elif text_upper.startswith("CLEAR_DATABASE") or text_upper.startswith("/CLEAR_DATABASE") or text_upper.startswith("CLEARDB") or text_upper.startswith("/CLEARDB"):
                    await self.clear_database(text_upper)
                    return
                elif text_upper.startswith("FIXHISTORY") or text_upper.startswith("/FIXHISTORY"):
                    await self.fix_historical_entries(text_upper)
                    return

                logger.info(f"Received DM from Admin. Processing Signal.")
                await self.process_message(event, is_mock_override=False)

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
        # Default to False unless overridden or MOCK prefix used
        is_mock = is_mock_override
            
        reply_msg = await event.get_reply_message()
        reply_context = reply_msg.message if reply_msg else ""
        
        # Explicit MOCK Command
        if text.lstrip().upper().startswith("MOCK"):
            is_mock = True
            # Strip "MOCK" from text so parser works
            # "MOCK LONG BTC..." -> "LONG BTC..."
            text = text.lstrip()[4:].strip()
            logger.info(f"Explicit MOCK command detected. Forced Mock Mode.")
        
        log_prefix = "[MOCK] " if is_mock else ""
        logger.info(f"{log_prefix}Processing message {msg_id} (Edit: {is_edit}): {text[:50]}...")

        # Parse
        data = await parse_message(text, reply_context)
        data['raw_message'] = text # Inject raw text for advanced processing
        
        if data['type'] == 'TRADE_CALL':
            # Check DB to allow edits ONLY if we haven't processed this msg_id yet
            # Determine symbol from data to store in reserve
            symbol = data.get('symbol', 'UNKNOWN')
            
            # ATTEMPT TO RESERVE TRADE ID FIRST (Prevents Race Conditions)
            is_reserved = await reserve_trade(msg_id, symbol)
            
            if not is_reserved:
                # Could be a duplicate OR an edit to an existing trade.
                # If existing, check if we should allow edit (not implemented complex logic yet), 
                # but generally we ignore duplicates to prevent double execution.
                logger.info(f"Ignored duplicate/edited TRADE_CALL {msg_id} (Already processed/reserved).")
            else:
                try:
                    await self.handle_trade_call(msg_id, data, is_mock)
                except Exception as e:
                    logger.error(f"Error handling trade call {msg_id}: {e}")
                    # Optional: Release reservation or mark as FAILED?
                    # For now, it stays as PROCESSING which blocks retries, which is safer than double execution.

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
        
        # Validate & Correct Symbol (e.g. BONK -> 1000BONKUSDT)
        symbol = await self.exchange.validate_symbol(symbol)
        logger.info(f"Symbol resolved to: {symbol}")
            
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
        
        # Take Profit Handling
        tp_price = None
        tp_list = data.get('tp', [])
        if tp_list:
            # Scale the first TP for the order
            tp_price = self.risk_manager.scale_price(tp_list[0], market_price)
            # Scale all TPs for logging/display
            scaled_tps = [self.risk_manager.scale_price(tp, market_price) for tp in tp_list]
            tp_display = ", ".join([str(tp) for tp in scaled_tps])
        else:
            tp_display = "None"

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
        
        # Variable Risk Sizing
        risk_scalar = 1.0
        raw_msg = data.get('raw_message', '').upper()
        if "0.5R" in raw_msg or "HALF RISK" in raw_msg or "0.5 R" in raw_msg:
             risk_scalar = 0.5
             logger.info(f"📉 Half Risk detected (0.5R). Scaling leverage/risk by 50%.")

        leverage = self.risk_manager.calculate_leverage(exec_price, sl_price, risk_scalar=risk_scalar)
        
        # Place Order
        if is_mock:
            logger.info(f"[MOCK] Skipping execution for {symbol}")
            await self.notifier.send(
                f"🧪 **MOCK TRADE DETECTED**\n"
                f"Action: {action} {direction} {symbol}\n"
                f"**Entry:** {exec_price}\n"
                f"**Leverage:** {leverage}x\n"
                f"**Size:** ${position_size_usdt:.2f} ({15 if balance <= 20000 else 'Tiered'}% Margin)\n"
                f"**TP:** {tp_display}\n"
                f"**SL:** {sl_price}\n"
                f"**Reason:** {reason}"
            )
            # Storing allows testing updates. Let's store with status "MOCK"
            await update_trade_full(msg_id, "MOCK_ORDER_ID", symbol, entry_price, sl_price, tp_price=tp_price, status="MOCK")
            return

        amount = (position_size_usdt * leverage) / exec_price
        side = 'buy' if direction.upper() == 'LONG' else 'sell'
        
        # SAFETY: Convert MARKET to MARKETABLE LIMIT (1% Slippage)
        final_order_type = action
        final_price = exec_price
        
        if action == 'MARKET':
             final_order_type = 'LIMIT'
             slippage = 0.01 # 1%
             if side == 'buy':
                 final_price = market_price * (1 + slippage)
             else:
                 final_price = market_price * (1 - slippage)
             logger.info(f"🛡️ Converted MARKET -> LIMIT for Safety. Price: {market_price} -> {final_price:.5f} (1% Buffer)")

        logger.info(f"Placing {final_order_type} {direction} on {symbol} x{leverage}. Price: {final_price}, TP: {tp_price}, SL: {sl_price}")
        
        try:
            # We always pass 'limit' as order_type if we converted it
            order_type_str = final_order_type.lower()
            
            order = await self.exchange.place_order(
                symbol, side, amount, leverage, 
                sl_price=sl_price, tp_price=tp_price, 
                price=final_price, 
                order_type=order_type_str
            )
            
            if order:
                # Capture Actual Fill Price if available
                fill_price = entry_price # Default to plan
                if order.get('average'):
                    fill_price = float(order['average'])
                elif order.get('price'):
                     # fallback for limit orders (might not be filled yet, but better than signal entry)
                     fill_price = float(order['price'])
                
                # UPDATE the reserved trade (PROCESSING -> OPEN)
                db_notes = f"Risk: {risk_scalar}R" if risk_scalar != 1.0 else None
                await update_trade_full(msg_id, order['id'], symbol, fill_price, sl_price, tp_price=tp_price, status="OPEN", position_side=direction, leverage=leverage, notes=db_notes)
                
                risk_note = f"\n**Risk:** {risk_scalar}R" if risk_scalar != 1.0 else ""
                await self.notifier.send(f"🟢 {final_order_type} Order Opened: {symbol} at {fill_price} with {leverage}x.\n**TP:** {tp_display}\n**SL:** {sl_price}\n**Margin:** ${position_size_usdt:.2f}{risk_note}\nReason: {reason}")
            else:
                # Should not happen if place_order raises on error, but handled for safety
                await self.notifier.send(f"⚠️ Execution failed for {symbol} (Unknown reason/None returned).")
        except Exception as e:
            logger.error(f"Execution failed for {symbol}: {e}")
            await self.notifier.send(f"⚠️ Execution failed for {symbol}:\n`{str(e)}`")

    # ... (Rest of monitor_trade_updates, handle_update etc. - unchanged) ...

    # Update send_performance_stats above this line...
    # Update clear_database below...
            
    async def clear_database(self, command_text=""):
        """Clears all trades (Requires Confirmation)."""
        # Parse command: /cleardb [confirm]
        args = command_text.split()
        if len(args) > 1 and args[1].upper() == "CONFIRM":
            try:
                await clear_all_trades()
                await self.notifier.send("🗑️ **Database Cleared.** All trade history has been wiped.")
            except Exception as e:
                await self.notifier.send(f"⚠️ Failed to clear database: {e}")
        else:
            await self.notifier.send("⚠️ **Caution:** This will wipe all trade history.\nTo proceed, type: `/cleardb confirm`")

    async def handle_update(self, msg_id, data, reply_msg_id=None, is_mock=False):
        # 1. Try to get symbol from Parser (if specific coin mentioned)
        symbol = data.get('symbol')
        
        trade = None
        if symbol:
            symbol = symbol.replace("#", "").replace("$", "").upper()
            if not symbol.endswith("USDT"): symbol += "USDT"

        # 2. Try to find trade by Reply ID
        if reply_msg_id and not trade:
            trade = await get_trade_by_msg_id(reply_msg_id)
        
        # 3. If still no trade, try to find the latest OPEN trade for that symbol in DB
        if not trade and symbol:
             trades = await get_all_open_trades()
             for t in trades:
                 if t['symbol'] == symbol:
                     trade = t
                     break

        # 4. 🕵️ NEW: If STILL no DB trade, check the exchange directly for a manual trade!
        if not trade and symbol:
            pos = await self.exchange.get_position(symbol)
            if pos:
                logger.info(f"Manual position found on exchange for {symbol}. Creating temporary context.")
                trade = {
                    'message_id': -1, # Dummy ID so DB queries fail gracefully
                    'symbol': symbol,
                    'order_id': None,
                    'status': 'OPEN'
                }

        if not trade:
            logger.info(f"Update ignored: Could not find original trade for reply {reply_msg_id} or symbol {symbol}")
            if symbol:
                await self.notifier.send(f"⚠️ Could not find an open trade for {symbol} in the DB or Exchange.")
            return

        action = data['action']
        symbol = trade['symbol']
        order_id = trade.get('order_id') # Use .get() since manual trades have None

        if is_mock or trade['status'] == 'MOCK':
            # Mock update
            await self.notifier.send(f"🧪 **MOCK UPDATE**\nAction: {action}\nValue: {data.get('value')}\n(No exchange action taken)")
            if action in ["CLOSE_FULL", "BOOK_R"]:
                 await close_trade_db(trade['message_id'])
            return

        if action == "MOVE_SL":
            new_sl = data['value']
            
            # Handle Special String Values (ENTRY, BE, LIQ)
            if isinstance(new_sl, str):
                new_sl_upper = new_sl.upper()
                if new_sl_upper in ["ENTRY", "BE", "BREAKEVEN", "LIQ", "LIQUIDATION"]:
                     position = await self.exchange.get_position(symbol)
                     if not position:
                         await self.notifier.send(f"⚠️ Cannot move SL to {new_sl_upper}: No active position found for {symbol}.")
                         return

                     if new_sl_upper in ["ENTRY", "BE", "BREAKEVEN"]:
                         real_entry = float(position['entryPrice'])
                         pos_side = position.get('side', '').lower()
                         buffer_pct = 0.0013  # 0.13% gap to cover fees
                         
                         if pos_side == 'long':
                             new_sl = real_entry * (1 + buffer_pct)
                         elif pos_side == 'short':
                             new_sl = real_entry * (1 - buffer_pct)
                         else:
                             new_sl = real_entry
                         
                     elif new_sl_upper in ["LIQ", "LIQUIDATION"]:
                         liq_price = float(position['liquidationPrice'])
                         if liq_price <= 0:
                             await self.notifier.send(f"⚠️ Cannot move SL to Liq: Liquidation price is 0 or invalid.")
                             return
                         new_sl = liq_price
            
            if not isinstance(data['value'], str) or (isinstance(data['value'], str) and data['value'].upper() not in ["ENTRY", "BE", "LIQ", "BREAKEVEN", "LIQUIDATION"]):
                 market_price = await self.exchange.get_market_price(symbol)
                 new_sl = self.risk_manager.scale_price(new_sl, market_price)
            
            result = await self.exchange.update_sl(symbol, new_sl)
            
            if isinstance(result, tuple):
                success, msg = result
            else:
                success, msg = result, "Unknown Error"

            if success:
                await self.notifier.send(f"🟡 Signal Edited: Updated SL for {symbol} to {new_sl}.")
            else:
                 await self.notifier.send(f"⚠️ Failed to update SL for {symbol}. Reason: {msg}")
            
        elif action in ["CLOSE_FULL", "BOOK_R"]:
            if action == "BOOK_R" and data.get('value'):
                r_multiple = data['value']
                logger.info(f"Booking {r_multiple}R.")
            
            await self.exchange.cancel_all_orders(symbol)
            success = await self.exchange.close_position(symbol)
            
            if success:
                last_trade = await self.exchange.get_last_trade(symbol)
                final_price = 0.0
                realized_pnl = 0.0
                
                if last_trade:
                    final_price = float(last_trade.get('price', 0.0))
                    if 'info' in last_trade and 'profit' in last_trade['info']:
                        realized_pnl = float(last_trade['info']['profit'])
                    elif 'info' in last_trade and 'cRealizedPL' in last_trade['info']:
                        realized_pnl = float(last_trade['info']['cRealizedPL'])
                    elif 'realizedPnl' in last_trade:
                         realized_pnl = float(last_trade['realizedPnl'] or 0.0)

                net_pnl_data = await self.exchange.get_last_closed_pnl(symbol)
                if net_pnl_data:
                    realized_pnl = net_pnl_data['pnl']
                    final_price = net_pnl_data['exit_price']

                # Use message_id gracefully (ignores if -1 dummy ID)
                await close_trade_db(trade['message_id'], exit_price=final_price, pnl=realized_pnl)
                
                current_price = await self.exchange.get_market_price(symbol)
                display_price = final_price if final_price > 0 else current_price
                
                bal_data = await self.exchange.get_balance()
                new_equity = bal_data['equity']
                
                reason_str = f"Take Profit ({realized_pnl:.2f} PnL)" if realized_pnl >= 0 else f"Stop Loss ({realized_pnl:.2f} PnL)"
                
                await self.notifier.send(f"🔴 Trade Closed: {symbol} at {display_price}. Equity: ${new_equity:.2f}.\n{reason_str}")
            else:
                await self.notifier.send(f"⚠️ Failed to close (or no position for) {symbol}.")

        elif action == "CANCEL":
            if order_id:
                logger.info(f"Cancelling specific order {order_id} for {symbol}")
                success = await self.exchange.cancel_order(symbol, order_id)
                if success:
                    await self.notifier.send(f"🚫 Cancelled Order `{order_id}` for {symbol}.")
                else:
                    await self.notifier.send(f"⚠️ Failed to cancel order `{order_id}` (It might be filled or already cancelled).")
            else:
                logger.info(f"Cancelling ALL orders for {symbol}")
                await self.exchange.cancel_all_orders(symbol)
                await self.notifier.send(f"🚫 Cancelled all open orders for {symbol}.")

        elif action == "MOVE_TP":
            new_tp = data['value']
            if not isinstance(new_tp, str):
                 market_price = await self.exchange.get_market_price(symbol)
                 new_tp = self.risk_manager.scale_price(new_tp, market_price)
            
            result = await self.exchange.update_tp(symbol, new_tp)
            
            if isinstance(result, tuple):
                success, msg = result
            else:
                 success, msg = result, "Unknown Error"

            if success:
                await self.notifier.send(f"🎯 Signal Edited: Updated TP for {symbol} to {new_tp}.")
            else:
                await self.notifier.send(f"⚠️ Failed to update TP for {symbol}. Reason: {msg}")

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
            "**Signals (DM Me):**\n"
            "• `LONG BTC ENTRY ...` -> **Real Trade**\n"
            "• `MOCK LONG BTC ENTRY ...` -> **Simulation Only**\n"
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
                data = prices.get(s, {'last': 0.0, 'percentage': 0.0, 'daily_pct': 0.0})
                p = data['last']
                pct_roll = data['percentage'] # Rolling 24h
                pct_daily = data.get('daily_pct', 0.0) # Daily Candle
                
                # Format: Price (24h: +x% | Day: +y%)
                icon = "🟢" if pct_daily >= 0 else "🔴"
                
                msg += (
                    f"• {s.replace('USDT', '')}:  `${p:,.2f}` {icon}\n"
                    f"   └ 24h: `{pct_roll:+.2f}%` | Day: `{pct_daily:+.2f}%`\n"
                )
                
            msg += "\n**Metals:**\n"
            for s in targets[8:]:
                data = prices.get(s, {'last': 0.0, 'percentage': 0.0, 'daily_pct': 0.0})
                p = data['last']
                pct_roll = data['percentage']
                pct_daily = data.get('daily_pct', 0.0)
                
                icon = "🟢" if pct_daily >= 0 else "🔴"
                
                msg += (
                    f"• {s.replace('USDT', '')}:  `${p:,.2f}` {icon}\n"
                    f"   └ 24h: `{pct_roll:+.2f}%` | Day: `{pct_daily:+.2f}%`\n"
                )
                
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
                logger.info("💓 Trade Monitor Pulse... Checking positions.")
                
                current_pos_list = await self.exchange.get_all_positions()
                current_positions = {p['symbol']: p for p in current_pos_list}
                
                # Check for CLOSED positions (In last_positions but NOT in current_positions)
                for symbol, old_pos in last_positions.items():
                    if symbol not in current_positions:
                        # Position Closed!
                        logger.info(f"Detected closure for {symbol}. Fetching details...")
                        
                        # Fetch Last Trade to get PnL/Reason
                        last_trade = await self.exchange.get_last_trade(symbol)
                        price = 0.0
                        pnl = 0.0
                        
                        if last_trade:
                            price = float(last_trade.get('price', 0.0))
                            # realisedPnl is often in the trade history
                            if 'info' in last_trade and 'profit' in last_trade['info']:
                                pnl = float(last_trade['info']['profit'])
                            elif 'info' in last_trade and 'cRealizedPL' in last_trade['info']:
                                pnl = float(last_trade['info']['cRealizedPL']) # Bitget V2 key?
                            elif 'realizedPnl' in last_trade: # CCXT unified
                                pnl = float(last_trade['realizedPnl'] or 0.0)

                            # Fetch Accurate Net PnL (including fees) via Position History
                            net_pnl_data = await self.exchange.get_last_closed_pnl(symbol)
                            if net_pnl_data:
                                pnl = net_pnl_data['pnl']
                                price = net_pnl_data['exit_price']
                                logger.info(f"Updated with Net PnL: {pnl} (Exit: {price})")

                            icon = "🟢" if pnl > 0 else "🔴"
                            reason = "Take Profit 🎯" if pnl > 0 else "Stop Loss 🛑"
                            
                            await self.notifier.send(
                                f"🔔 **Position Closed: {symbol}**\n"
                                f"{icon} **PnL:** ${pnl:.2f} ({reason})\n"
                                f"📉 **Exit Price:** {price}\n"
                            )
                        else:
                            await self.notifier.send(f"🔔 **Position Closed: {symbol}** (Details unavailable)")

                        # --- DB UPDATE FIX ---
                        # Update DB status to CLOSED even if manual/external close
                        try:
                            open_trades = await get_all_open_trades()
                            # Find the trade for this symbol
                            # Normalization: BTC/USDT:USDT -> BTCUSDT
                            normalized_symbol = symbol.replace("/", "").replace(":", "").split("USDT")[0] + "USDT"
                            
                            # We might have multiple if bugged, but usually one OPEN per symbol
                            target_trade = next((t for t in open_trades if t['symbol'] == normalized_symbol or t['symbol'] == symbol), None)
                            
                            if target_trade:
                                await close_trade_db(target_trade['message_id'], exit_price=price, pnl=pnl)
                                logger.info(f"DB Update: Marked {symbol} (Msg {target_trade['message_id']}) as CLOSED.")
                            else:
                                logger.warning(f"Could not find OPEN trade in DB for {symbol} to close.")
                        except Exception as db_e:
                            logger.error(f"Failed to update DB on manual close: {db_e}")

                # Update Cache
                last_positions = current_positions
                
                # --- 🕵️ AUTO-DETECT MANUAL TRADES ---
                try:
                    open_trades_sync = await get_all_open_trades()
                    db_symbols = [t['symbol'] for t in open_trades_sync]
                    
                    for pos_sym, pos_data in current_positions.items():
                        norm_pos = pos_sym.replace("/", "").replace(":", "").split("USDT")[0] + "USDT"
                        
                        # If the exchange has a position NOT in our DB, it was made manually!
                        if norm_pos not in db_symbols:
                            import time
                            # Generate a unique negative message ID for the database
                            dummy_id = -int(time.time() * 1000) % 1000000000
                            entry_px = float(pos_data.get('entryPrice', 0))
                            side = pos_data.get('side', 'long').upper()
                            leverage = pos_data.get('leverage', 1)
                            
                            # --- 🕵️ AUTO-DETECT MANUAL TRADES ---
                            try:
                                # Fetch active SL/TP for this manual trade
                                tp_list, sl_list = await self.exchange.get_active_tp_sl(pos_sym)
                                sl_val = sl_list[0] if sl_list else 0.0
                                tp_val = tp_list[0] if tp_list else 0.0
                                
                                # Add to Database so it tracks PnL and History natively
                                await store_trade(dummy_id, "MANUAL", norm_pos, entry_px, sl_val, tp_val, "OPEN", trade_type="MANUAL")
                                await update_trade_full(dummy_id, "MANUAL", norm_pos, entry_px, sl_val, tp_price=tp_val, status="OPEN", position_side=side, leverage=leverage, notes="Manual Trade")
                                
                                sl_display = f" (SL: {sl_val})" if sl_val > 0 else " (No SL)"
                                logger.info(f"Detected Manual Trade {norm_pos}{sl_display}. Added to DB with ID {dummy_id}.")
                                await self.notifier.send(f"🕵️ **Manual Trade Detected:** {norm_pos} ({side} x{leverage})\nBot is now tracking this position. You can manage it via chat!{sl_display}")
                            except Exception as e:
                                logger.error(f"Error in manual trade detection: {e}")
                            
                            # Add to db_symbols to prevent duplicate alerts
                            db_symbols.append(norm_pos)
                except Exception as detect_e:
                    logger.error(f"Manual Trade Detection Error: {detect_e}")
                # ----------------------------------
                
                # --- SYNC OPEN TRADES ENTRY PRICE ---
                try:
                    open_trades_sync = await get_all_open_trades()
                    for t in open_trades_sync:
                        # Find matching position
                        # DB Symbol is normalized (BTCUSDT), Pos Symbol might be (BTC/USDT:USDT)
                        # We need to find if 't' corresponds to any key in current_positions
                        
                        match_pos = None
                        for pos_sym, pos_data in current_positions.items():
                             norm_pos = pos_sym.replace("/", "").replace(":", "").split("USDT")[0] + "USDT"
                             if norm_pos == t['symbol']:
                                 match_pos = pos_data
                                 break
                        
                        if match_pos:
                            real_entry = float(match_pos.get('entryPrice', 0.0))
                            if real_entry == 0.0 and 'openPriceAvg' in match_pos:
                                    real_entry = float(match_pos['openPriceAvg'])
                            
                            db_entry = float(t['entry_price'])
                            
                            diff_pct = 0
                            if db_entry > 0:
                                diff_pct = abs(real_entry - db_entry) / db_entry
                                
                            if real_entry > 0 and diff_pct > 0.001: # 0.1% diff
                                await update_trade_entry(t['message_id'], real_entry)
                                logger.info(f"🔄 Synced Entry Price for {t['symbol']}: {db_entry} -> {real_entry} (Diff: {diff_pct:.2%})")

                            # --- SYNC STOP LOSS & TAKE PROFIT (ONLY IF MISSING) ---
                            # User requested: Do not update if already exists (to keep original R calculation)
                            db_sl = float(t.get('sl_price') or 0.0)
                            db_tp = float(t.get('tp_price') or 0.0)

                            if db_sl == 0.0 or db_tp == 0.0:
                                # Fetch active SL/TP from exchange
                                # We use pos_sym if match_pos was found (which it was, at line 805)
                                # But we need pos_sym again. Let's find it.
                                
                                # Find original pos_sym from current_positions
                                current_pos_sym = next((ps for ps, pd in current_positions.items() if pd == match_pos), t['symbol'])
                                
                                ex_tp_list, ex_sl_list = await self.exchange.get_active_tp_sl(current_pos_sym)
                                ex_sl = ex_sl_list[0] if ex_sl_list else 0.0
                                ex_tp = ex_tp_list[0] if ex_tp_list else 0.0

                                # Update SL if 0
                                if db_sl == 0.0 and ex_sl > 0:
                                    await update_trade_sl(t['message_id'], ex_sl)
                                    logger.info(f"🎯 Synced Missing SL for {t['symbol']}: {ex_sl}")
                                    await self.notifier.send(f"🎯 **Stop Loss Sync:** Detected SL for {t['symbol']} at {ex_sl}. Now tracking performance!")
                                
                                # Update TP if 0
                                if db_tp == 0.0 and ex_tp > 0:
                                    await update_trade_tp(t['message_id'], ex_tp)
                                    logger.info(f"🎯 Synced Missing TP for {t['symbol']}: {ex_tp}")

                            # --- AUTO BREAK-EVEN at 0.5R ---
                            db_entry = float(t.get('entry_price') or 0.0)
                            db_sl = float(t.get('sl_price') or 0.0)
                            
                            # Only proceed if we have valid entry and original SL from DB
                            if db_entry > 0 and db_sl > 0 and db_entry != db_sl:
                                current_pos_sym = next((ps for ps, pd in current_positions.items() if pd == match_pos), t['symbol'])
                                ex_tp_list, ex_sl_list = await self.exchange.get_active_tp_sl(current_pos_sym)
                                current_ex_sl = ex_sl_list[0] if ex_sl_list else 0.0
                                
                                mark_price = float(match_pos.get('markPrice', 0.0))
                                side = match_pos.get('side', '').lower()
                                
                                direction = 1 if side == 'long' else -1
                                risk = abs(db_entry - db_sl)
                                
                                if mark_price > 0 and risk > 0:
                                    current_r = ((mark_price - db_entry) / risk) * direction
                                    
                                    if current_r >= 0.5:
                                        # Calculate BE price with small buffer (e.g., 0.13% to cover fees)
                                        buffer_pct = 0.0013
                                        be_price = db_entry * (1 + buffer_pct) if side == 'long' else db_entry * (1 - buffer_pct)
                                        
                                        # Check if current SL is NOT already at BE or better
                                        needs_update = False
                                        if current_ex_sl == 0.0:
                                            needs_update = True
                                        elif side == 'long' and current_ex_sl < be_price * 0.999: # 0.1% tolerance
                                            needs_update = True
                                        elif side == 'short' and current_ex_sl > be_price * 1.001:
                                            needs_update = True
                                            
                                        if needs_update:
                                            logger.info(f"🛡️ Auto-BE Triggered for {t['symbol']} at {current_r:.2f}R! Moving SL to {be_price}")
                                            
                                            # Update SL on exchange
                                            result = await self.exchange.update_sl(current_pos_sym, be_price)
                                            success = result[0] if isinstance(result, tuple) else result
                                            
                                            if success:
                                                # Update DB with new SL (Optional: Might want to keep original for stats, but updating keeps it in sync)
                                                await update_trade_sl(t['message_id'], be_price)
                                                await self.notifier.send(f"🛡️ **Auto-BE Triggered!**\n{t['symbol']} reached {current_r:.2f}R. SL moved to entry ({be_price:.4f}).")

                except Exception as sync_loop_e:
                    logger.error(f"Sync Loop Error: {sync_loop_e}")
                # ------------------------------------
                
            except Exception as e:
                logger.error(f"Trade monitor error: {e}")
            
            await asyncio.sleep(60) # Poll every 60s

    async def send_database_records(self):
        """Sends the last 20 trades from the database."""
        try:
            trades = await get_recent_trades(20)
            
            if not trades:
                await self.notifier.send("📭 Database is empty.")
                return
            
            msg = "📚 **Trade History (Last 20)**\n\n"
            
            for t in trades:
                # Format Timestamps
                def fmt_ts(raw):
                    if not raw: return "?"
                    return str(raw)

                start_ts = fmt_ts(t.get('timestamp'))
                end_ts = fmt_ts(t.get('closed_timestamp')) if t['status'] == "CLOSED" else None

                # NEW: Determine Trade Type Icon
                t_type = t.get('trade_type', 'AUTO')
                type_icon = "🤖 Auto" if t_type == "AUTO" else "🖐 Manual"

                # Header Construction
                header = f"🟢 [OPEN] **{t['symbol']}** ({type_icon})"
                if t['status'] == "CLOSED":
                     # Dynamic Icon based on Pnl
                     pnl = t.get('pnl', 0)
                     icon = "🟢" if pnl > 0 else "🔴"
                     header = f"{icon} [CLOSED] **{t['symbol']}** ({type_icon})"

                # Basic Info
                row_msg = (
                    f"{header}\n"
                    f"   🌐 Entry: {t['entry_price']} | SL: {t['sl_price']}\n"
                    f"   🕒 Open: {start_ts}\n"
                )
                
                # Closed details
                if t['status'] == "CLOSED":
                    exit_p = t.get('exit_price', 0)
                    pnl = t.get('pnl', 0)
                    
                    # Calculate R for display
                    r_display = ""
                    try:
                        entry = float(t['entry_price'])
                        sl = float(t['sl_price'])
                        exit_px = float(exit_p or 0)
                        if entry != sl and exit_px > 0:
                            risk = abs(entry - sl)
                            direction = 1 if sl < entry else -1
                            r_val = (exit_px - entry) / risk * direction
                            r_display = f" | R: {r_val:.2f}"
                    except:
                        pass

                    row_msg += f"   🏁 Exit: {exit_p} | PnL: ${pnl:.2f}{r_display}\n"
                    if end_ts:
                         row_msg += f"   🕒 Close: {end_ts}\n"
                
                row_msg += "\n"
                msg += row_msg
            
            if len(msg) > 4000:
                msg = msg[:4000] + "\n...(truncated)"
                
            await self.notifier.send(msg)
            
        except Exception as e:
            logger.error(f"DB Fetch failed: {e}")
            await self.notifier.send(f"⚠️ Error fetching history: {e}")

    async def send_performance_stats(self, command_text):
        """Sends performance stats report."""
        try:
            # Parse Args: /performance [month] [year]
            parts = command_text.strip().split()
            
            if len(parts) > 1:
                # Custom Lookup
                try:
                    import datetime
                    month_str = parts[1]
                    year_str = parts[2] if len(parts) > 2 else str(datetime.datetime.now().year)
                    
                    month_map = {
                        "JAN": 1, "JANUARY": 1, "FEB": 2, "FEBRUARY": 2, "MAR": 3, "MARCH": 3,
                        "APR": 4, "APRIL": 4, "MAY": 5, "JUN": 6, "JUNE": 6, "JUL": 7, "JULY": 7,
                        "AUG": 8, "AUGUST": 8, "SEP": 9, "SEPTEMBER": 9, "OCT": 10, "OCTOBER": 10,
                        "NOV": 11, "NOVEMBER": 11, "DEC": 12, "DECEMBER": 12
                    }
                    
                    month = month_map.get(month_str.upper(), 0)
                    if month == 0: month = int(month_str)
                    year = int(year_str)
                    
                    stat = await get_monthly_stats(month, year)
                    
                    a_wr = (stat['auto_wins'] / stat['auto_total'] * 100) if stat['auto_total'] > 0 else 0
                    m_wr = (stat['manual_wins'] / stat['manual_total'] * 100) if stat['manual_total'] > 0 else 0
                    
                    msg = (
                        f"📊 **Performance: {stat['label']}**\n"
                        f"--------------------------\n"
                        f"🤖 Auto: WR {a_wr:.1f}% ({stat['auto_wins']}/{stat['auto_total']}) | R: {stat['auto_r']:.2f}\n"
                        f"🖐 Manual: WR {m_wr:.1f}% ({stat['manual_wins']}/{stat['manual_total']}) | R: {stat['manual_r']:.2f}\n"
                    )
                    await self.notifier.send(msg)
                    return
                    
                except Exception as e:
                    await self.notifier.send(f"⚠️ Invalid format. Use: `/performance April 2026` or `/performance`")
                    return

            # Default: Dashboard
            stats = await get_stats_report()
            
            def fmt_stat(key):
                data = stats[key]
                label = data['label']
                a_tot = data['auto_total']
                a_win = data['auto_wins']
                a_wr = (a_win / a_tot * 100) if a_tot > 0 else 0
                a_r = data['auto_r']
                
                m_tot = data['manual_total']
                m_win = data['manual_wins']
                m_wr = (m_win / m_tot * 100) if m_tot > 0 else 0
                m_r = data['manual_r']
                
                return (
                    f"**{label}**\n"
                    f"🤖 Auto: WR {a_wr:.1f}% ({a_win}/{a_tot}) | R: {a_r:.2f}\n"
                    f"🖐 Manual: WR {m_wr:.1f}% ({m_win}/{m_tot}) | R: {m_r:.2f}"
                )
                
            msg = "📊 **Performance Dashboard**\n\n"
            msg += fmt_stat('monthly') + "\n\n"
            msg += fmt_stat('prev_monthly') + "\n\n"
            msg += fmt_stat('quarterly') + "\n\n"
            msg += fmt_stat('prev_quarterly') + "\n\n"
            msg += fmt_stat('yearly') + "\n\n"
            msg += fmt_stat('prev_yearly') + "\n\n"
            msg += fmt_stat('lifetime')
            
            await self.notifier.send(msg)

        except Exception as e:
            logger.error(f"Stats Error: {e}")
            await self.notifier.send(f"⚠️ Error fetching stats: {e}")
            
    async def clear_database(self, command_text=""):
        """Clears all trades (Requires Confirmation)."""
        # Parse command: /cleardb [confirm]
        args = command_text.split()
        if len(args) > 1 and args[1].upper() == "CONFIRM":
            try:
                await clear_all_trades()
                await self.notifier.send("🗑️ **Database Cleared.** All trade history has been wiped.")
            except Exception as e:
                await self.notifier.send(f"⚠️ Failed to clear database: {e}")
        else:
            await self.notifier.send("⚠️ **Caution:** This will wipe all trade history.\nTo proceed, type: `/cleardb confirm`")

    async def fix_historical_entries(self, command_text):
        """
        Manually syncs entry prices for CLOSED trades by checking Order History.
        Usage: /fixhistory [limit] (default 20)
        """
        try:
            parts = command_text.split()
            limit = int(parts[1]) if len(parts) > 1 else 20
            
            await self.notifier.send(f"⏳ **Starting History Fix** (Limit: {limit})...\nThis may take a moment.")
            
            trades = await get_recent_trades(limit)
            updated_count = 0
            
            for t in trades:
                if t['status'] != 'CLOSED': continue
                
                symbol = t['symbol']
                # Normalize for bitget if needed, but fetch_orders usually takes the slash format or unified
                # We'll try the stored symbol first
                
                try:
                    # Fetch orders around the trade timestamp
                    # optimization: fetch last N orders
                    history = await self.exchange.exchange.fetch_orders(symbol, limit=20)
                    
                    # Find the OPEN order (buy/sell that matches entry criteria)
                    # We look for the order that was filled closest to 'timestamp'
                    # timestamp string: "2026-02-16 07:19:43" (WIB) -> Need to be careful with Timezones
                    
                    # Simplification: Look for the FIRST filled order that is BEFORE the closed_timestamp (if exists) 
                    # OR just look for the order with the price that is NOT the same as current DB entry
                    
                    # Let's find the order with status='closed' and side matching logical entry side
                    # Long: Buy, Short: Sell
                    
                    # Filter history for this symbol's entry order
                    # It's hard to map exactly 1-to-1 without order_id if order_id was missed.
                    # But we have order_id in DB!
                    
                    matched_order = None
                    if t['order_id']:
                        # If we have order ID, search for it specifically
                        try:
                            matched_order = await self.exchange.exchange.fetch_order(t['order_id'], symbol)
                        except:
                            pass
                    
                    if not matched_order:
                        # Fallback: Find most recent filled order before this trade's close time?
                        # Taking a risk here: Just find the latest 'closed' order that looks like an entry
                        # For now, let's rely on Order ID if present, otherwise skip to be safe
                        continue

                    if matched_order:
                        real_entry = float(matched_order.get('average') or matched_order.get('price') or 0)
                        db_entry = float(t['entry_price'])
                        
                        if real_entry > 0 and abs(real_entry - db_entry) / db_entry > 0.001:
                            await update_trade_entry(t['message_id'], real_entry)
                            updated_count += 1
                            logger.info(f"Fixed History {symbol}: {db_entry} -> {real_entry}")

                except Exception as inner_e:
                    logger.warning(f"Failed to fix {symbol}: {inner_e}")
                    
            await self.notifier.send(f"✅ **History Fix Complete.**\nUpdated {updated_count} trades.")
            
        except Exception as e:
             await self.notifier.send(f"⚠️ History Fix Failed: {e}")

    async def send_help(self):
        msg = (
            "🤖 **Trading Bot Commands**\n\n"
            "**/status** - System status & PnL\n"
            "**/trades** - Open positions details\n"
            "**/database** - Last 20 trade entries\n"
            "**/performance** - Win Rate & R Dashboard\n"
            "**/performance [Month] [Year]** - Specific month stats\n"
            "**/fixhistory** - Sync historical entry prices\n"
            "**/cleardb** - Wipe all trade history\n"
            "**/market** - BTC Price Check\n"
            "**/help** - Show this menu\n"
        )
        await self.notifier.send(msg)

