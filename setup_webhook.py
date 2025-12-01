# setup_webhook.py - Run this ONCE after deploying to Render

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'BF.settings')
django.setup()

from django.conf import settings
import requests

WEBHOOK_URL = f"https://bollyfun.onrender.com/telegram/webhook/"  # Your Render URL
BOT_TOKEN = settings.TELEGRAM_BOT_TOKEN

def setup_webhook():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    data = {'url': WEBHOOK_URL}
    
    response = requests.post(url, data=data)
    result = response.json()
    
    if result.get('ok'):
        print(f"✅ Webhook set successfully!")
        print(f"Webhook URL: {WEBHOOK_URL}")
    else:
        print(f"❌ Failed to set webhook: {result.get('description')}")

if __name__ == '__main__':
    setup_webhook()