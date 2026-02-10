import aiosqlite
import logging
from config import DB_NAME

logger = logging.getLogger(__name__)

async def init_db():
    """Initialize the database with the trades table."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                message_id INTEGER PRIMARY KEY,
                order_id TEXT,
                symbol TEXT,
                entry_price REAL,
                sl_price REAL,
                tp_price REAL,
                status TEXT,
                exit_price REAL,
                pnl REAL,
                timestamp DATETIME
            )
        ''')
        # Migrations
        try:
            await db.execute('ALTER TABLE trades ADD COLUMN exit_price REAL')
        except:
            pass
        try:
            await db.execute('ALTER TABLE trades ADD COLUMN pnl REAL')
        except:
            pass
        try:
            await db.execute('ALTER TABLE trades ADD COLUMN timestamp DATETIME')
        except:
            pass
        await db.commit()
    logger.info("Database initialized.")

async def store_trade(message_id, order_id, symbol, entry_price, sl_price, tp_price=None, status="OPEN"):
    """Store a new trade with WIB timestamp."""
    # Current Time (UTC) -> WIB (UTC+7)
    from datetime import datetime, timezone, timedelta
    
    # Correct way to get WIB time
    tz_wib = timezone(timedelta(hours=7))
    now_wib = datetime.now(timezone.utc).astimezone(tz_wib)
    
    # Store as string "YYYY-MM-DD HH:MM:SS" (Naive-like but correct Time)
    ts_str = now_wib.strftime('%Y-%m-%d %H:%M:%S')
    
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            INSERT INTO trades (message_id, order_id, symbol, entry_price, sl_price, tp_price, status, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (message_id, order_id, symbol, entry_price, sl_price, tp_price, status, ts_str))
        await db.commit()

async def get_trade_by_msg_id(message_id):
    """Retrieve trade details by Telegram message ID."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT * FROM trades WHERE message_id = ?', (message_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                # Handle varying schema if robust columns managed by row_factory or index
                # Basic fetch with index might be risky if columns added in middle, but we appended.
                # Safer to use row_factory or access by index assuming append.
                # Schema: msg_id, order_id, symbol, entry, sl, tp, status, exit, pnl, timestamp
                return {
                    "message_id": row[0],
                    "order_id": row[1],
                    "symbol": row[2],
                    "entry_price": row[3],
                    "sl_price": row[4],
                    "tp_price": row[5],
                    "status": row[6]
                    # We can add others but existing consumers might not need them yet
                }
            return None

async def update_trade_order_id(message_id, order_id):
    """Update the order_id for a trade (e.g. after entry)."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE trades SET order_id = ? WHERE message_id = ?', (order_id, message_id))
        await db.commit()

async def update_trade_sl(message_id, sl_price):
    """Update the SL price."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE trades SET sl_price = ? WHERE message_id = ?', (sl_price, message_id))
        await db.commit()
        
async def close_trade_db(message_id, exit_price=0.0, pnl=0.0):
    """Mark a trade as CLOSED in the DB with PnL data."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE trades SET status = "CLOSED", exit_price = ?, pnl = ? WHERE message_id = ?', (exit_price, pnl, message_id))
        await db.commit()

async def get_open_trade_count():
    """Get the number of currently OPEN trades."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT COUNT(*) FROM trades WHERE status = "OPEN"') as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def get_all_open_trades():
    """Get all currently OPEN trades."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM trades WHERE status = "OPEN"') as cursor:
            rows = await cursor.fetchall()
            trades = []
            for row in rows:
                trades.append({
                    "message_id": row["message_id"],
                    "order_id": row["order_id"],
                    "symbol": row["symbol"],
                    "entry_price": row["entry_price"],
                    "sl_price": row["sl_price"],
                    "tp_price": row["tp_price"],
                    "status": row["status"],
                    "timestamp": row["timestamp"]
                })
            return trades

async def get_recent_trades(limit=20):
    """Get the last N trades (excluding MOCK)."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM trades WHERE status != "MOCK" ORDER BY timestamp DESC LIMIT ?', (limit,)) as cursor:
            rows = await cursor.fetchall()
            trades = []
            for row in rows:
                trades.append({
                    "message_id": row["message_id"],
                    "order_id": row["order_id"],
                    "symbol": row["symbol"],
                    "entry_price": row["entry_price"],
                    "sl_price": row["sl_price"],
                    "tp_price": row["tp_price"],
                    "status": row["status"],
                    "timestamp": row["timestamp"]
                })
            return trades
