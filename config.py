import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
TELEGRAM_CHANNEL_ID = int(os.getenv("TELEGRAM_CHANNEL_ID", "-1001252615519"))
# Destination can be a username (str) or ID (int). Default to 'me' if missing.
NOTIFICATION_USER_ID = os.getenv("NOTIFICATION_USER_ID", "me")
try:
    NOTIFICATION_USER_ID = int(NOTIFICATION_USER_ID)
except ValueError:
    pass # Keep as string if not an int (e.g. "me" or "@username")

# Bitget
BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# App
DB_NAME = "trading_bot.db"
