import signal

# ... imports ...

async def shutdown(signal, loop, notifier):
    """Cleanup tasks tied to the service's shutdown."""
    logger.info(f"Received exit signal {signal.name}...")
    try:
        await notifier.send(f"🛑 **Bot Stopping...** ({signal.name})")
    except Exception as e:
        logger.error(f"Could not send shutdown msg: {e}")
        
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]

    logger.info(f"Cancelling {len(tasks)} outstanding tasks")
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()

def handle_exception(loop, context):
    msg = context.get("exception", context["message"])
    logger.error(f"Caught exception: {msg}")

async def main():
    # ... (Init DB, Clients as before) ...
    # Initialize DB
    await init_db()

    # 1. Listener Client (Userbot)
    logger.info("Starting Listener Client (Userbot)...")
    listener_client = TelegramClient('listener_session', TELEGRAM_API_ID, TELEGRAM_API_HASH)
    await listener_client.start()

    # 2. Notifier Client (Bot API)
    logger.info("Starting Notifier Client (Bot API)...")
    notifier_client = TelegramClient('notifier_session', TELEGRAM_API_ID, TELEGRAM_API_HASH)
    await notifier_client.start(bot_token=BOT_TOKEN)
    
    # Initialize Modules
    notifier = Notifier(notifier_client)
    listener = TelegramListener(listener_client, notifier_client, notifier)

    # Startup Notification is handled inside listener.start() now -> notify_last_message + send_status

    # Start Keep-Alive
    asyncio.create_task(keep_alive_task())

    # Start Listener Logic
    await listener.start()
    
    logger.info("Bot is running...")

    # Wait for stop signal
    # We use a Future to keep the loop running until a signal is received
    stop_event = asyncio.Event()

    # Register signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown(s, loop, notifier)))

    try:
        # Run clients in background until disconnected OR stop_event
        await asyncio.gather(
            listener_client.run_until_disconnected(),
            notifier_client.run_until_disconnected()
        )
    except asyncio.CancelledError:
        pass
    finally:
        logger.info("Shutting down... Closing Exchange Connection.")
        await listener.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
