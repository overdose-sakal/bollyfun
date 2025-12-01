# movies/management/commands/cleanup_messages.py

import logging
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings

# Ensure you are importing your model correctly
from movies.models import SentFile 

from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    """
    Django management command to delete Telegram messages older than 24 hours.
    To be run as a separate Render Cron Job.
    """
    help = 'Deletes SentFile messages on Telegram that are older than 24 hours.'
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting scheduled Telegram message cleanup..."))

        # Time threshold: 24 hours ago
        deletion_threshold = timezone.now() - timedelta(hours=24)
        
        # Initialize the synchronous Bot object for management commands
        try:
            bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to initialize Telegram Bot: {e}"))
            return

        # 1. Find records to delete
        messages_to_delete = SentFile.objects.filter(
            date_sent__lt=deletion_threshold
        )
        
        self.stdout.write(self.style.NOTICE(
            f"Found {messages_to_delete.count()} messages older than 24 hours to process."
        ))

        deleted_count = 0
        
        for sent_file in messages_to_delete:
            try:
                # 2. Delete on Telegram
                bot.delete_message(
                    chat_id=sent_file.user_chat_id, 
                    message_id=sent_file.message_id
                )
                
                # 3. Delete the record from the Django DB
                sent_file.delete()
                deleted_count += 1
                
            except TelegramError as e:
                # Handle cases where the message was already deleted by the user
                if 'message to delete not found' in str(e):
                    sent_file.delete()
                    self.stdout.write(self.style.WARNING(
                        f"Message {sent_file.message_id} already deleted on Telegram. Removed DB record."
                    ))
                else:
                    self.stdout.write(self.style.ERROR(
                        f"Failed to delete message {sent_file.message_id} in chat {sent_file.user_chat_id}: {e}"
                    ))
            
        self.stdout.write(self.style.SUCCESS(
            f'✅ Cleanup finished. Successfully deleted {deleted_count} messages on Telegram and DB.'
        ))