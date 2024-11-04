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

def get_tgtg_client(email: Optional[str] = None, access_token: Optional[str] = None,
                    refresh_token: Optional[str] = None, user_id: Optional[str] = None,
                    cookie: Optional[str] = None) -> TgtgClient:
    """Initialize TgtgClient with credentials from environment variables or parameters."""
    email = os.getenv('TGTG_EMAIL') or email
    access_token = os.getenv('TGTG_ACCESS_TOKEN') or access_token
    refresh_token = os.getenv('TGTG_REFRESH_TOKEN') or refresh_token
    user_id = os.getenv('TGTG_USER_ID') or user_id
    cookie = os.getenv('TGTG_COOKIE') or cookie
    
    if email:
        return TgtgClient(email=email)
    else:
        return TgtgClient(
            access_token=access_token,
            refresh_token=refresh_token,
            user_id=user_id,
            cookie=cookie
        )

# Alert history management
ALERT_HISTORY_FILE = "alert_history.json"

def load_alert_history():
    if os.path.exists(ALERT_HISTORY_FILE):
        try:
            with open(ALERT_HISTORY_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def save_alert_history(history):
    with open(ALERT_HISTORY_FILE, 'w') as f:
        json.dump(history, f)

def can_send_alert(item_id, history):
    if item_id not in history:
        return True
    
    last_alert_time = datetime.fromisoformat(history[item_id])
    current_time = datetime.now()
    
    # Check if 2 hours have passed since the last alert
    return (current_time - last_alert_time) >= timedelta(hours=2)

async def send_messages(bot, chat_id, text_message, latitude, longitude):
    await bot.send_message(chat_id=chat_id, text=text_message)
    await bot.send_location(chat_id=chat_id, latitude=latitude, longitude=longitude)

async def run_bot(messages, chat_id, api_key):
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

async def main():
    # Initialize with environment variables
    tgtg_client = get_tgtg_client()
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    api_key = os.getenv('TELEGRAM_API_KEY')

    # Load alert history
    alert_history = load_alert_history()

    # Set up timezone
    utc = pytz.utc
    mdt = pytz.timezone('America/Edmonton')
    
    # Get favorites from TGTG
    favorites = tgtg_client.get_favorites()

    messages = []
    for entry in favorites:
        items_available = entry.get('items_available')
        item_id = entry['item'].get('item_id')
        display_name = entry.get('display_name')
        pickup_interval = entry.get('pickup_interval')
        pickup_location = entry.get('pickup_location')
        
        if items_available > 0 and can_send_alert(item_id, alert_history):
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
                
                # Send the alert
                await run_bot(messages, chat_id, api_key)
                
                # Update the alert history
                alert_history[item_id] = datetime.now().isoformat()
                save_alert_history(alert_history)
                
                messages = []

if __name__ == "__main__":
    asyncio.run(main())