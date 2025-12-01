# movies/management/commands/cleanup_old_files.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from movies.models import SentFile
from telegram import Bot
from django.conf import settings

class Command(BaseCommand):
    help = 'Delete files that should have been auto-deleted'

    def handle(self, *args, **options):
        bot = Bot(settings.TELEGRAM_BOT_TOKEN)
        old_files = SentFile.objects.filter(delete_at__lt=timezone.now())
        
        deleted_count = 0
        for file in old_files:
            try:
                bot.delete_message(chat_id=file.chat_id, message_id=file.message_id)
                file.delete()
                deleted_count += 1
            except Exception as e:
                self.stdout.write(f"Failed to delete {file.id}: {e}")
        
        self.stdout.write(f"Deleted {deleted_count} old files")