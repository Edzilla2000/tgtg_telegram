#!/usr/bin/env python
from tgtg import TgtgClient
from telegram import Bot
from telegram.ext import Application
import json
from datetime import datetime, timedelta
import os
import pytz
import asyncio
from typing import Optional
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class TGTGError(Exception):
    """Base exception class for TGTG bot errors"""
    pass

class TGTGAuthError(TGTGError):
    """Authentication error"""
    pass

def get_tgtg_client(email: Optional[str] = None, access_token: Optional[str] = None,
                    refresh_token: Optional[str] = None,
                    cookie: Optional[str] = None) -> TgtgClient:
    """Initialize TgtgClient with credentials from environment variables or parameters."""
    try:
        email = os.getenv('TGTG_EMAIL') or email
        access_token = os.getenv('TGTG_ACCESS_TOKEN') or access_token
        refresh_token = os.getenv('TGTG_REFRESH_TOKEN') or refresh_token
        cookie = os.getenv('TGTG_COOKIE') or cookie
        
        if email:
            logger.info("Initializing TGTG client with email")
            return TgtgClient(email=email)
        else:
            logger.info("Initializing TGTG client with tokens")
            return TgtgClient(
                access_token=access_token,
                refresh_token=refresh_token,
                cookie=cookie
            )
    except Exception as e:
        logger.error(f"Failed to initialize TGTG client: {str(e)}")
        raise TGTGError(f"TGTG client initialization failed: {str(e)}")

# Alert history management
ALERT_HISTORY_FILE = "alert_history.json"

def load_alert_history():
    if os.path.exists(ALERT_HISTORY_FILE):
        try:
            with open(ALERT_HISTORY_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Error reading alert history file: {str(e)}")
            raise TGTGError(f"Failed to read alert history: {str(e)}")
    return {}

def save_alert_history(history):
    try:
        with open(ALERT_HISTORY_FILE, 'w') as f:
            json.dump(history, f)
    except Exception as e:
        logger.error(f"Error saving alert history: {str(e)}")
        raise TGTGError(f"Failed to save alert history: {str(e)}")

def can_send_alert(item_id, history):
    if item_id not in history:
        return True
    
    last_alert_time = datetime.fromisoformat(history[item_id])
    current_time = datetime.now()
    
    return (current_time - last_alert_time) >= timedelta(hours=2)

async def send_messages(bot, chat_id, text_message, latitude, longitude):
    try:
        await bot.send_message(chat_id=chat_id, text=text_message)
        await bot.send_location(chat_id=chat_id, latitude=latitude, longitude=longitude)
        logger.info(f"Successfully sent notification for location: {latitude}, {longitude}")
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {str(e)}")
        raise TGTGError(f"Failed to send Telegram message: {str(e)}")

async def run_bot(messages, chat_id, api_key):
    try:
        message_text = []
        stored_location = None
       
        for line in messages:
            if line.startswith("Location:"):
                coordinates = line.replace("Location: ", "").split(",")
                lat, lng = float(coordinates[0]), float(coordinates[1])
                stored_location = (lat, lng)
            else:
                message_text.append(line)
       
        message_text = "\n".join(message_text)
       
        application = Application.builder().token(api_key).build()
        async with application:
            if stored_location:
                await send_messages(
                    application.bot,
                    chat_id,
                    message_text,
                    stored_location[0],
                    stored_location[1]
                )
    except Exception as e:
        logger.error(f"Error in run_bot: {str(e)}")
        raise TGTGError(f"Bot execution failed: {str(e)}")

def check_auth_error(error_str: str) -> bool:
    """Check if error string indicates an authentication error"""
    auth_error_indicators = ['401', 'UNAUTHORIZED', 'auth', 'token']
    return any(indicator.lower() in error_str.lower() for indicator in auth_error_indicators)

async def async_main() -> int:
    try:
        logger.info("Starting TGTG notification bot")
        
        # Initialize with environment variables
        tgtg_client = get_tgtg_client()
        chat_id = os.getenv('TELEGRAM_CHAT_ID')
        api_key = os.getenv('TELEGRAM_API_KEY')

        if not chat_id or not api_key:
            raise TGTGError("Missing required environment variables: TELEGRAM_CHAT_ID or TELEGRAM_API_KEY")

        # Load alert history
        alert_history = load_alert_history()
        logger.info("Alert history loaded successfully")

        # Set up timezone
        utc = pytz.utc
        mdt = pytz.timezone('America/Edmonton')
        
        # Get favorites from TGTG
        logger.info("Fetching favorites from TGTG")
        try:
            favorites = tgtg_client.get_favorites()
        except Exception as e:
            error_str = str(e)
            if check_auth_error(error_str):
                raise TGTGAuthError("TGTG authentication failed - invalid or expired tokens")
            raise TGTGError(f"Failed to fetch favorites: {error_str}")

        logger.info(f"Found {len(favorites)} favorite items")

        messages = []
        for entry in favorites:
            try:
                items_available = entry.get('items_available')
                item_id = entry['item'].get('item_id')
                display_name = entry.get('display_name')
                pickup_interval = entry.get('pickup_interval')
                pickup_location = entry.get('pickup_location')
                
                if items_available > 0 and can_send_alert(item_id, alert_history):
                    logger.info(f"Found available items for {display_name} (ID: {item_id})")
                    
                    if pickup_location and 'location' in pickup_location:
                        location = pickup_location['location']
                    
                    if pickup_interval and 'start' in pickup_interval and 'end' in pickup_interval:
                        start_utc = datetime.strptime(pickup_interval['start'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=utc)
                        end_utc = datetime.strptime(pickup_interval['end'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=utc)
                        start_mdt = start_utc.astimezone(mdt)
                        end_mdt = end_utc.astimezone(mdt)
                        readable_start = start_mdt.strftime("%Y-%m-%d %I:%M %p %Z")
                        readable_end = end_mdt.strftime("%Y-%m-%d %I:%M %p %Z")
                    
                        messages = [
                            "",
                            "Shop: " + display_name,
                            "Pickup time: " + readable_start + "/" + readable_end,
                            "Location: " + str(location.get('latitude')) + "," + str(location.get('longitude'))
                        ]
                        
                        await run_bot(messages, chat_id, api_key)
                        
                        alert_history[item_id] = datetime.now().isoformat()
                        save_alert_history(alert_history)
                        
                        messages = []
            except Exception as e:
                logger.error(f"Error processing entry for {display_name}: {str(e)}")
                raise TGTGError(f"Error processing entry: {str(e)}")

        return 0

    except TGTGAuthError as e:
        logger.error(f"Authentication error: {str(e)}")
        return 1
    except TGTGError as e:
        logger.error(f"TGTG error: {str(e)}")
        return 2
    except Exception as e:
        logger.error(f"Fatal error in main function: {str(e)}")
        return 3

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(async_main())
        sys.exit(exit_code)
    except Exception as e:
        logger.error(f"Critical error: {str(e)}")
        sys.exit(4)