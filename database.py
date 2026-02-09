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
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.commit()
    logger.info("Database initialized.")

async def store_trade(message_id, order_id, symbol, entry_price, sl_price, tp_price=None, status="OPEN"):
    """Store a new trade."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            INSERT INTO trades (message_id, order_id, symbol, entry_price, sl_price, tp_price, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (message_id, order_id, symbol, entry_price, sl_price, tp_price, status))
        await db.commit()

async def get_trade_by_msg_id(message_id):
    """Retrieve trade details by Telegram message ID."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT * FROM trades WHERE message_id = ?', (message_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "message_id": row[0],
                    "order_id": row[1],
                    "symbol": row[2],
                    "entry_price": row[3],
                    "sl_price": row[4],
                    "tp_price": row[5],
                    "status": row[6]
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
        
async def close_trade_db(message_id):
    """Mark a trade as CLOSED in the DB."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE trades SET status = "CLOSED" WHERE message_id = ?', (message_id,))
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
    """Get the last N trades."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?', (limit,)) as cursor:
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
