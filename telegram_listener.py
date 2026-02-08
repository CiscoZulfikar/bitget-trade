from telethon import TelegramClient, events
import logging
import asyncio
from config import TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_CHANNEL_ID, NOTIFICATION_USER_ID
from parser import parse_message
from risk_manager import RiskManager
from exchange_handler import ExchangeHandler
from database import store_trade, get_trade_by_msg_id, update_trade_order_id, update_trade_sl, close_trade_db, get_open_trade_count, get_all_open_trades
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
                elif text_upper in ["CURRENT_TRADE", "/TRADES", "TRADES"]:
                    await self.send_open_trades()
                    return

                logger.info(f"Received DM from Admin. Processing as Mock Signal.")
                await self.process_message(event, is_mock_override=True)

        logger.info(f"Listener attached to channel {self.channel_id} and Bot DMs...")
        
        # Fetch and notify last message on startup
        await self.notify_last_message()
        
        # Start Periodic Status Update (30m)
        asyncio.create_task(self.periodic_status_task())
        
        # We don't run_until_disconnected here anymore, main does it


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

        # Check Max Trades
        open_trades_count = await get_open_trade_count()
        if open_trades_count >= 3:
             logger.warning(f"Skipping trade {symbol}: Max concurrent trades (3) reached.")
             await self.notifier.send(f"⚠️ Signal Skipped: Max concurrent trades reached (3). Ignored {symbol}.")
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
        trade = None
        if reply_msg_id:
            trade = await get_trade_by_msg_id(reply_msg_id)
        
        if not trade:
            logger.warning("Update received but original trade not found.")
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
            "\n"
            "**Mock Signals (DM Me):**\n"
            "`LONG BTC ENTRY 90000 SL 89000`\n"
            "`LIMIT SHORT ETH ENTRY 3000 SL 3100`"
        )
        await self.notifier.send(help_text)

    async def send_status(self):
        try:
            bal_data = await self.exchange.get_balance()
            free = bal_data['free']
            equity = bal_data['equity']
            count = await get_open_trade_count()
            await self.notifier.send(
                f"📊 **System Status**\n\n"
                f"💎 **Equity:** ${equity:.2f}\n"
                f"💵 **Free:** ${free:.2f}\n"
                f"📉 **Open Trades:** {count}/3"
            )
        except Exception as e:
            await self.notifier.send(f"⚠️ Could not fetch status: {e}")

    async def send_open_trades(self):
        trades = await get_all_open_trades()
        if not trades:
            await self.notifier.send("📭 No open trades.")
            return

        msg = "📉 **Current Trades**\n\n"
        for t in trades:
            msg += f"• **{t['symbol']}** | Entry: {t['entry_price']} | SL: {t['sl_price']}\n"
        
        await self.notifier.send(msg)

    async def periodic_status_task(self):
        """Runs every 30 minutes to send a status update."""
        while True:
            await asyncio.sleep(1800) # 30 minutes
            try:
                await self.send_status()
            except Exception as e:
                logger.error(f"Periodic update failed: {e}")

