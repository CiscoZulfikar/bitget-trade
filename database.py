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
        try:
            await db.execute('ALTER TABLE trades ADD COLUMN closed_timestamp DATETIME')
        except:
            pass
        try:
            await db.execute('ALTER TABLE trades ADD COLUMN position_side TEXT')
        except:
            pass
        try:
            await db.execute('ALTER TABLE trades ADD COLUMN leverage INTEGER')
        except:
            pass
        try:
            await db.execute('ALTER TABLE trades ADD COLUMN notes TEXT')
        except:
            pass
        await db.commit()
    logger.info("Database initialized.")

async def store_trade(message_id, order_id, symbol, entry_price, sl_price, tp_price=None, status="OPEN"):
    """Store a new trade with WIB timestamp."""
    from datetime import datetime, timezone, timedelta
    
    tz_wib = timezone(timedelta(hours=7))
    now_wib = datetime.now(timezone.utc).astimezone(tz_wib)
    
    ts_str = now_wib.strftime('%Y-%m-%d %H:%M:%S')
    
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            INSERT INTO trades (message_id, order_id, symbol, entry_price, sl_price, tp_price, status, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (message_id, order_id, symbol, entry_price, sl_price, tp_price, status, ts_str))
        await db.commit()

async def reserve_trade(message_id, symbol):
    """Reserve a trade ID to prevent double execution. Returns True if successful."""
    # Current Time (UTC) -> WIB (UTC+7)
    from datetime import datetime, timezone, timedelta
    tz_wib = timezone(timedelta(hours=7))
    now_wib = datetime.now(timezone.utc).astimezone(tz_wib)
    ts_str = now_wib.strftime('%Y-%m-%d %H:%M:%S')

    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute('''
                INSERT INTO trades (message_id, symbol, status, timestamp)
                VALUES (?, ?, 'PROCESSING', ?)
            ''', (message_id, symbol, ts_str))
            await db.commit()
        return True
    except Exception as e:
        # Likely UNIQUE constraint failed -> Trade already exists
        logger.warning(f"Failed to reserve trade {message_id}: {e}")
        return False

async def update_trade_full(message_id, order_id, symbol, entry_price, sl_price, tp_price=None, status="OPEN", position_side="LONG", leverage=None, notes=None):
    """Update a reserved trade with full details."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            UPDATE trades 
            SET order_id = ?, symbol = ?, entry_price = ?, sl_price = ?, tp_price = ?, status = ?, position_side = ?, leverage = ?, notes = ?
            WHERE message_id = ?
        ''', (order_id, symbol, entry_price, sl_price, tp_price, status, position_side, leverage, notes, message_id))
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
                    "status": row[6],
                    "position_side": row[11] if len(row) > 11 else ("LONG" if row[4] < row[3] else "SHORT") # Fallback
                }
            return None

async def update_trade_order_id(message_id, order_id):
    """Update the order_id for a trade (e.g. after entry)."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE trades SET order_id = ? WHERE message_id = ?', (order_id, message_id))
        await db.commit()

async def update_trade_entry(message_id, entry_price):
    """Update the entry price for a trade (Sync with Exchange)."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE trades SET entry_price = ? WHERE message_id = ?', (entry_price, message_id))
        await db.commit()

async def update_trade_sl(message_id, sl_price):
    """Update the SL price."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE trades SET sl_price = ? WHERE message_id = ?', (sl_price, message_id))
        await db.commit()

async def close_trade_db(message_id, exit_price=0.0, pnl=0.0):
    """Mark a trade as CLOSED in the DB with PnL data."""
    # Current Time (UTC) -> WIB (UTC+7)
    from datetime import datetime, timezone, timedelta
    tz_wib = timezone(timedelta(hours=7))
    now_wib = datetime.now(timezone.utc).astimezone(tz_wib)
    ts_str = now_wib.strftime('%Y-%m-%d %H:%M:%S')

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE trades SET status = "CLOSED", exit_price = ?, pnl = ?, closed_timestamp = ? WHERE message_id = ?', (exit_price, pnl, ts_str, message_id))
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
                    "timestamp": row["timestamp"],
                    "position_side": row["position_side"] if "position_side" in row.keys() else ("LONG" if row["sl_price"] < row["entry_price"] else "SHORT")
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
                    "timestamp": row["timestamp"],
                    "exit_price": row["exit_price"],
                    "pnl": row["pnl"],
                    "closed_timestamp": row.keys().__contains__("closed_timestamp") and row["closed_timestamp"] or None,
                    "position_side": row["position_side"] if "position_side" in row.keys() else ("LONG" if row["sl_price"] < row["entry_price"] else "SHORT")
                })
            return trades

async def get_stats_report():
    """
    Calculates Win Rate and Total R for:
    - Current Month, Previous Month
    - Current Quarter, Previous Quarter
    - Current Year, Previous Year
    - Lifetime
    Returns a dict with breakdown and labels.
    """
    from datetime import datetime, timedelta
    
    # Define periods
    now = datetime.utcnow()
    # Shift to WIB (UTC+7)
    now_wib = now + timedelta(hours=7)
    
    # Dates
    curr_month_start = now_wib.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    last_day_prev_month = curr_month_start - timedelta(days=1)
    prev_month_start = last_day_prev_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    q_month = (now_wib.month - 1) // 3 * 3 + 1
    curr_quarter_start = now_wib.replace(month=q_month, day=1, hour=0, minute=0, second=0, microsecond=0)
    
    last_day_prev_quarter = curr_quarter_start - timedelta(days=1)
    prev_q_month = (last_day_prev_quarter.month - 1) // 3 * 3 + 1
    prev_quarter_start = last_day_prev_quarter.replace(month=prev_q_month, day=1, hour=0, minute=0, second=0, microsecond=0)
    
    curr_year_start = now_wib.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_year_start = curr_year_start.replace(year=curr_year_start.year - 1)
    prev_year_end = curr_year_start - timedelta(seconds=1)

    def get_q_label(date):
        q = (date.month - 1) // 3 + 1
        return f"Q{q} {date.year}"

    labels = {
        "monthly": now_wib.strftime("%b %Y"),
        "prev_monthly": last_day_prev_month.strftime("%b %Y"),
        "quarterly": get_q_label(now_wib),
        "prev_quarterly": get_q_label(last_day_prev_quarter),
        "yearly": now_wib.strftime("%Y"),
        "prev_yearly": prev_year_start.strftime("%Y"),
        "lifetime": "Lifetime"
    }

    stats = {k: {"label": v, "wins": 0, "total": 0, "total_r": 0.0} for k, v in labels.items()}

    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM trades WHERE status = "CLOSED" AND pnl IS NOT NULL') as cursor:
            rows = await cursor.fetchall()
            
            for row in rows:
                try:
                    ts_str = str(row['timestamp'])
                    if '.' in ts_str: ts_str = ts_str.split('.')[0]
                    trade_date = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
                except:
                    continue

                # Basic Data
                entry = float(row['entry_price'] or 0)
                exit_px = float(row['exit_price'] or 0)
                sl = float(row['sl_price'] or 0)
                pnl = float(row['pnl'] or 0)
                
                if entry == 0 or sl == 0: continue

                if "position_side" in row.keys() and row["position_side"]:
                    direction = row["position_side"]
                else:
                    direction = "LONG" if sl < entry else "SHORT"
                
                risk = abs(entry - sl)
                if risk == 0: continue
                
                r_value = 0.0
                if direction == "LONG":
                    r_value = (exit_px - entry) / risk
                else:
                    r_value = (entry - exit_px) / risk
                
                if r_value > 20 or r_value < -20: r_value = 0
                
                is_win = pnl > 0
                
                def update(key):
                    stats[key]['total'] += 1
                    if is_win: stats[key]['wins'] += 1
                    stats[key]['total_r'] += r_value

                # Lifetime
                update('lifetime')
                
                # Monthly
                if trade_date >= curr_month_start:
                    update('monthly')
                elif prev_month_start <= trade_date < curr_month_start:
                    update('prev_monthly')
                    
                # Quarterly
                if trade_date >= curr_quarter_start:
                    update('quarterly')
                elif prev_quarter_start <= trade_date < curr_quarter_start:
                    update('prev_quarterly')
                    
                # Yearly
                if trade_date >= curr_year_start:
                    update('yearly')
                elif prev_year_start <= trade_date <= prev_year_end:
                    update('prev_yearly')

    return stats

async def get_monthly_stats(month, year):
    """
    Get stats for a specific month and year.
    month: 1-12 (int)
    year: e.g. 2026 (int)
    """
    from datetime import datetime, timedelta
    import calendar
    
    start_date = datetime(year, month, 1)
    # End date calculation
    last_day = calendar.monthrange(year, month)[1]
    end_date = datetime(year, month, last_day, 23, 59, 59)
    
    label = start_date.strftime("%B %Y")
    stat = {"label": label, "wins": 0, "total": 0, "total_r": 0.0}
    
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM trades WHERE status = "CLOSED" AND pnl IS NOT NULL') as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                try:
                    ts_str = str(row['timestamp'])
                    if '.' in ts_str: ts_str = ts_str.split('.')[0]
                    trade_date = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
                except:
                    continue
                    
                if start_date <= trade_date <= end_date:
                    entry = float(row['entry_price'] or 0)
                    exit_px = float(row['exit_price'] or 0)
                    sl = float(row['sl_price'] or 0)
                    pnl = float(row['pnl'] or 0)
                    
                    if entry == 0 or sl == 0: continue

                    if "position_side" in row.keys() and row["position_side"]:
                        direction = row["position_side"]
                    else:
                        direction = "LONG" if sl < entry else "SHORT"

                    risk = abs(entry - sl)
                    if risk == 0: continue
                    r_value = (exit_px - entry) / risk if direction == "LONG" else (entry - exit_px) / risk
                    
                    if r_value > 20 or r_value < -20: r_value = 0
                    
                    stat['total'] += 1
                    if pnl > 0: stat['wins'] += 1
                    stat['total_r'] += r_value
                    
    return stat

async def clear_all_trades():
    """Wipes all trade history."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('DELETE FROM trades')
        await db.commit()
    return True
