import asyncio
import argparse
import logging
from parser import parse_message
from exchange_handler import ExchangeHandler
from risk_manager import RiskManager

# Setup minimal logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

async def inject_signal(message_text):
    print(f"\n📩 INJECTING MOCK MESSAGE: \"{message_text}\"")
    print("---------------------------------------------------")

    # 1. PARSE
    print("1️⃣  Parsing Message with Gemini...")
    try:
        data = await parse_message(message_text)
        print(f"   ✅ Parsed Data: {data}")
    except Exception as e:
        print(f"   ❌ Parsing Failed: {e}")
        return

    if data.get('type') != 'TRADE_CALL':
        print(f"   ⚠️  Message is not a TRADE_CALL (Type: {data.get('type')})")
        return

    # Extract Data
    symbol = data['symbol']
    direction = data['direction']
    entry = data['entry']
    sl = data['sl']
    
    # Clean Symbol logic from listener
    symbol = symbol.replace("#", "").replace("$", "").upper()
    if not symbol.endswith("USDT"):
        symbol += "USDT"

    print(f"   ℹ️  Extracted: {direction} {symbol} @ {entry} (SL: {sl})")

    # 2. INIT HANDLERS
    print("\n2️⃣  Initializing Exchange & Risk Manager...")
    try:
        exchange = ExchangeHandler()
        risk_manager = RiskManager()
    except Exception as e:
        print(f"   ❌ Failed to init: {e}")
        return

    # 3. FETCH DATA
    print("\n3️⃣  Fetching Live Market Data...")
    try:
        market_price = await exchange.get_market_price(symbol)
        balance = await exchange.get_balance()
        print(f"   ✅ Market Price: {market_price}")
        print(f"   ✅ Wallet Balance: ${balance:.2f}")
    except Exception as e:
        print(f"   ❌ Failed to fetch data: {e}")
        await exchange.close()
        return

    # 4. LOGIC
    print("\n4️⃣  Running Risk Logic...")
    
    # Scale
    scaled_entry = risk_manager.scale_price(entry, market_price)
    scaled_sl = risk_manager.scale_price(sl, market_price)
    
    if scaled_entry != entry:
        print(f"   ℹ️  Scaled Entry: {entry} -> {scaled_entry}")

    # Decision Logic
    explicit_type = data.get('order_type', 'MARKET')
    action, decision_price, reason = risk_manager.determine_entry_action(scaled_entry, market_price, explicit_type)

    if action == 'ABORT':
        print(f"   ❌ TRADE ABORTED: {reason}")
        await exchange.close()
        return
    
    print(f"   ✅ Logic Decision: {action} ({reason})")

    # Calc
    exec_price = decision_price if action == 'LIMIT' else market_price
    pos_size_usdt = risk_manager.calculate_position_size(balance)
    leverage = risk_manager.calculate_leverage(exec_price, scaled_sl)
    amount_contracts = (pos_size_usdt * leverage) / exec_price

    print("\n---------------------------------------------------")
    print("📊 SIMULATED BOT OUTPUT")
    print("---------------------------------------------------")
    print(f"Action:         {action} {direction.upper()} {symbol}")
    print(f"Entry Price:    {exec_price}")
    print(f"Stop Loss:      {scaled_sl}")
    print(f"Leverage:       {leverage}x")
    print(f"Position Size:  ${pos_size_usdt:.2f} (Margin)")
    print(f"Total Value:    ${pos_size_usdt * leverage:.2f}")
    print(f"Contracts:      {amount_contracts:.4f}")
    print(f"Reason:         {reason}")
    print("---------------------------------------------------")
    print("✅ Logic Check Complete. (No Trade Executed)")

    await exchange.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inject a Mock Text Signal for Testing")
    parser.add_argument("message", type=str, help="Raw message text (quoted)")
    
    args = parser.parse_args()
    
    asyncio.run(inject_signal(args.message))
