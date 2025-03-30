#!/usr/bin/env python3
"""
Delta Bot Entrypoint

This script initializes and runs a Delta trading bot with an API server
for remote control and monitoring.
"""

import os
import logging
import asyncio
import signal
import sys
import json
from dotenv import load_dotenv

# Load environment variables first to get version info
load_dotenv()

# Bot version information
__version__ = os.getenv("BOT_VERSION", "1.0.0")
BOT_NAME = "Delta"

# Import the Delta bot
from Delta import Delta

# Import API module (will be created later)
from api import start_api, stop_api

# Global reference to the bot instance
delta_bot = None

async def main():
    """Main entry point for running the Delta bot."""
    global delta_bot
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("delta.log")
        ]
    )
    
    logger = logging.getLogger("DeltaBot")
    
    # Register signal handlers for graceful shutdown
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *args: shutdown())
    
    logger.info(f"Initializing {BOT_NAME} bot v{__version__}...")
    
    # Create the Delta bot instance
    delta_bot = Delta()
    
    # Load API configuration from environment
    api_host = os.getenv("API_HOST", "0.0.0.0")
    api_port = int(os.getenv("API_PORT", "8080"))
    api_enabled = os.getenv("API_ENABLED", "true").lower() in ("true", "1", "yes")
    
    # Start API server if enabled
    if api_enabled and os.environ.get('API_SECRET_KEY'):
        logger.info(f"Starting API server on {api_host}:{api_port}")
        await start_api(delta_bot, host=api_host, port=api_port)
        logger.info("API server started")
    else:
        logger.warning("API server is disabled (either API_SECRET_KEY not set or API_ENABLED=false)")
    
    # If autostart is enabled, start the bot
    autostart = os.getenv('AUTOSTART_BOT', 'true').lower() in ('true', '1', 'yes')
    if autostart:
        logger.info(f"Autostarting {BOT_NAME}...")
        try:
            # Start the Delta bot
            await delta_bot.start()
        except Exception as e:
            logger.error(f"Error starting {BOT_NAME}: {e}")
    else:
        logger.info(f"{BOT_NAME} initialized but not started (AUTOSTART_BOT is false)")
        # Keep the main task running even if the bot is not started
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Main task cancelled")

def shutdown():
    """Graceful shutdown of the Delta bot and API server."""
    global delta_bot
    
    logger = logging.getLogger("DeltaBot")
    logger.info("Shutting down...")
    
    # Schedule the stop_api coroutine
    loop = asyncio.get_event_loop()
    if loop.is_running():
        loop.create_task(stop_api())
    
    # Close all positions if requested
    if delta_bot:
        loop.create_task(delta_bot.exit_program(close_positions=True))
    
    # Force exit after a brief delay if not exited naturally
    def force_exit():
        logger.warning("Forcing exit...")
        sys.exit(1)
    
    # Schedule force exit after 15 seconds
    loop = asyncio.get_event_loop()
    loop.call_later(15, force_exit)

if __name__ == "__main__":
    try:
        print(f"\n{BOT_NAME} Bot v{__version__} - HyperVault Trading Bots")
        print("=" * 50)
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.getLogger("DeltaBot").info("Application terminated by user")
    except Exception as e:
        logging.getLogger("DeltaBot").error(f"Application error: {e}") 