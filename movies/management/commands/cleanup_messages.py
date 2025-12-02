# movies/management/commands/cleanup_messages.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from movies.models import SentFile
from telegram import Bot
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Delete Telegram messages that have passed their 24-hour expiration'

    def handle(self, *args, **options):
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        
        # Get all expired messages
        expired_files = SentFile.objects.filter(delete_at__lte=timezone.now())
        
        deleted_count = 0
        failed_count = 0
        
        self.stdout.write(f"Found {expired_files.count()} messages to delete")
        
        for sent_file in expired_files:
            try:
                # Delete the message
                bot.delete_message(
                    chat_id=sent_file.chat_id,
                    message_id=sent_file.message_id
                )
                
                # Remove from database
                sent_file.delete()
                deleted_count += 1
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ Deleted message {sent_file.message_id} for {sent_file.movie.title}'
                    )
                )
            except Exception as e:
                failed_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'❌ Failed to delete message {sent_file.message_id}: {str(e)}'
                    )
                )
                # Delete from DB anyway (message might already be deleted)
                sent_file.delete()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Cleanup complete: {deleted_count} deleted, {failed_count} failed'
            )
        )