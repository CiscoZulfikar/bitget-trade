from telethon import TelegramClient
import logging
from config import NOTIFICATION_USER_ID

logger = logging.getLogger(__name__)

class Notifier:
    def __init__(self, client: TelegramClient):
        self.client = client
        self.target = NOTIFICATION_USER_ID

    async def send(self, message):
        """Sends a message to the configured target."""
        try:
            # For Bot API, we can send to ID or username
            await self.client.send_message(self.target, message)
        except Exception as e:
            logger.error(f"Failed to send notification to {self.target}: {e}")
