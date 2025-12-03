# BF/asgi.py

import os
from django.core.asgi import get_asgi_application
from django.conf import settings

# Telegram Imports
import logging


# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'BF.settings')
django_asgi_app = get_asgi_application()
from movies.bot_handlers import handle_start_command

import logging
from telegram.ext import Application, CommandHandler

# --- TELEGRAM BOT INITIALIZATION ---
logger = logging.getLogger(__name__)

# Initialize the bot APPLICATION outside of any worker-specific function
try:
    # Use the token from settings
    BOT_TOKEN = settings.TELEGRAM_BOT_TOKEN
    
    # 1. Build the application
    telegram_app = Application.builder().token(BOT_TOKEN).updater(None).build()
    
    # 2. Add handlers
    telegram_app.add_handler(CommandHandler("start", handle_start_command))
    
    logger.info("✅ Telegram Bot Application initialized successfully in ASGI startup.")

except Exception as e:
    logger.error(f"❌ Critical error initializing Telegram Application: {e}")
    # Define a dummy application to prevent crashes if the bot fails to start
    telegram_app = None 


# The main application object
application = django_asgi_app

# Note: You must ensure 'python-telegram-bot' is listed in your requirements.txt (which it is)