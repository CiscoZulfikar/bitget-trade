import asyncio
import logging
from telethon import TelegramClient
from config import TELEGRAM_API_ID, TELEGRAM_API_HASH, BOT_TOKEN
from database import init_db
from telegram_listener import TelegramListener
from notifier import Notifier
from keep_alive import keep_alive_task

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

async def main():
    # Initialize DB
    await init_db()

    # 1. Listener Client (Userbot)
    # Listens to private/restricted channels using User Credentials
    logger.info("Starting Listener Client (Userbot)...")
    listener_client = TelegramClient('listener_session', TELEGRAM_API_ID, TELEGRAM_API_HASH)
    await listener_client.start()

    # 2. Notifier Client (Bot API)
    # Sends alerts using the Public Bot Token
    logger.info("Starting Notifier Client (Bot API)...")
    notifier_client = TelegramClient('notifier_session', TELEGRAM_API_ID, TELEGRAM_API_HASH)
    await notifier_client.start(bot_token=BOT_TOKEN)
    
    # Initialize Modules
    notifier = Notifier(notifier_client)
    # Pass BOTH clients to listener: 
    # listener_client for channel monitoring
    # notifier_client (bot) for DM monitoring
    listener = TelegramListener(listener_client, notifier_client, notifier)

    # Startup Notification (via Bot)
    await notifier.send("🤖 Trading Bot Started & Connected via Hybrid Mode.")

    # Start Keep-Alive
    asyncio.create_task(keep_alive_task())

    # Start Listener Logic
    await listener.start()

    # Keep both running
    logger.info("Bot is running...")
    
    # Keep both running
    logger.info("Bot is running...")
    
    try:
        # Run both clients until disconnected
        await asyncio.gather(
            listener_client.run_until_disconnected(),
            notifier_client.run_until_disconnected()
        )
    finally:
        logger.info("Shutting down... Closing Exchange Connection.")
        await listener.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
