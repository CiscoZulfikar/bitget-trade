import asyncio
import logging

logger = logging.getLogger(__name__)

async def keep_alive_task():
    """
    A background task that runs every 30 minutes to print a log message.
    This helps prevent the Oracle Cloud instance from being marked as idle.
    """
    while True:
        logger.info("Keep-alive: System is running...")
        await asyncio.sleep(1800)  # 30 minutes
