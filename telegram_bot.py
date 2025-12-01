# telegram_bot.py - WITH AUTO-DELETE AFTER 24 HOURS

import os
import sys
import uuid
import logging
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from asgiref.sync import sync_to_async

# Setup logging FIRST
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Django setup
logger.info("Setting up Django...")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'BF.settings')

try:
    import django
    django.setup()
    logger.info("✅ Django setup complete")
except Exception as e:
    logger.error(f"❌ Django setup failed: {e}")
    sys.exit(1)

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, JobQueue
from movies.models import DownloadToken, Movies, SentFile

logger.info("Imports successful")


async def delete_message_job(context: ContextTypes.DEFAULT_TYPE):
    """Job to delete a message after 24 hours"""
    job_data = context.job.data
    chat_id = job_data['chat_id']
    message_id = job_data['message_id']
    
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.info(f"🗑️ Deleted message {message_id} from chat {chat_id} after 24 hours")
        
        # Remove from database tracking
        await sync_to_async(SentFile.objects.filter(
            chat_id=chat_id, 
            message_id=message_id
        ).delete)()
        
    except Exception as e:
        logger.error(f"Failed to delete message {message_id}: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command with token parameter"""
    logger.info(f"📨 Received /start command from user {update.effective_user.id}")
    logger.info(f"Arguments: {context.args}")
    
    if not context.args:
        await update.message.reply_text(
            "🎬 Welcome to BollyFun!\n\n"
            "Get your download link from the website.\n\n"
            "⚠️ Note: Files will be automatically deleted after 24 hours for security."
        )
        logger.info("No arguments provided - sent welcome message")
        return

    token_str = context.args[0]
    
    # DEBUG: Log the received token
    logger.info(f"🔑 Received token string: {token_str}")
    logger.info(f"Token length: {len(token_str)}")

    # Fetch DB token using the string directly (Django handles UUID conversion)
    try:
        token = await sync_to_async(DownloadToken.objects.get)(token=token_str)
        
        # Access related fields safely with sync_to_async
        movie_title = await sync_to_async(lambda: token.movie.title if token.movie else "Unknown")()
        logger.info(f"✅ Found token for movie: {movie_title}, quality: {token.quality}")
    except DownloadToken.DoesNotExist:
        logger.error(f"❌ Token not found in database: {token_str}")
        
        # DEBUG: Check what tokens exist (safely)
        token_count = await sync_to_async(DownloadToken.objects.count)()
        logger.info(f"Total tokens in DB: {token_count}")
        
        await update.message.reply_text("❌ This link is invalid or has already been used.")
        return
    except Exception as e:
        logger.error(f"❌ Error fetching token: {str(e)}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text("❌ An error occurred. Please try again.")
        return

    # Token expiration check
    if not token.is_valid():
        await sync_to_async(token.delete)()
        await update.message.reply_text("⏰ This link has expired. Please generate a new one from the website.")
        return

    # Check if movie exists
    movie = await sync_to_async(lambda: token.movie)()
    if not movie:
        logger.error(f"❌ Token has no associated movie!")
        await sync_to_async(token.delete)()
        await update.message.reply_text("❌ Invalid token: No movie associated. Please generate a new link.")
        return
    
    quality = token.quality

    # Get file_id instead of message_id
    file_id = await sync_to_async(
        lambda: movie.SD_telegram_file_id if quality == "SD" else movie.HD_telegram_file_id
    )()
    
    if not file_id:
        logger.error(f"❌ No file ID found for {quality} quality")
        await update.message.reply_text(f"❌ Error: File not found for {quality} quality.")
        await sync_to_async(token.delete)()
        return

    # Send "processing" message
    processing_msg = await update.message.reply_text("⏳ Sending your file...")

    # Send file directly (not forward) so we can delete it later
    try:
        movie_title = await sync_to_async(lambda: movie.title)()
        
        # Send the document by file_id
        sent_message = await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=file_id,
            caption=f"🎬 **{movie_title}** ({quality})\n\n⚠️ This file will be automatically deleted in 24 hours."
        )
        
        await processing_msg.delete()
        
        await update.message.reply_text(
            f"✅ Your **{quality}** file for **{movie_title}** is above.\n\n"
            f"⏰ **Important:** This file will be automatically deleted after 24 hours for security reasons.\n"
            f"Please download it soon!",
            parse_mode="Markdown"
        )
        
        # Schedule deletion after 24 hours
        context.job_queue.run_once(
            delete_message_job,
            when=timedelta(hours=24),
            data={
                'chat_id': update.effective_chat.id,
                'message_id': sent_message.message_id
            },
            name=f"delete_{sent_message.message_id}"
        )
        
        # Track sent file in database
        await sync_to_async(SentFile.objects.create)(
            chat_id=update.effective_chat.id,
            message_id=sent_message.message_id,
            movie=movie,
            quality=quality,
            delete_at=timezone.now() + timedelta(hours=24)
        )
        
        logger.info(f"✅ File sent and scheduled for deletion in 24 hours")
        
        # Delete token after successful use
        await sync_to_async(token.delete)()
    
    except Exception as e:
        await processing_msg.delete()
        await update.message.reply_text(
            "❌ An error occurred while sending the file. Please try again."
        )
        logger.error(f"Error sending file: {str(e)}")
        import traceback
        traceback.print_exc()


def main():
    """Start the bot"""
    try:
        logger.info("🤖 Initializing bot application...")
        
        # Create application with your bot token
        application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
        logger.info(f"✅ Bot token loaded: {settings.TELEGRAM_BOT_TOKEN[:10]}...")

        # Add command handler
        application.add_handler(CommandHandler("start", start))
        logger.info("✅ Command handlers registered")

        # Start the bot
        logger.info("🚀 Starting bot polling...")
        logger.info(f"Bot username: @{settings.TELEGRAM_BOT_USERNAME}")
        logger.info("Bot is now running with 24-hour auto-delete! Press Ctrl+C to stop.")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == '__main__':
    main()