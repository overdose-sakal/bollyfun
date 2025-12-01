# movies/bot_handlers.py

import logging
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from asgiref.sync import sync_to_async
from telegram import Update
from telegram.ext import ContextTypes
from movies.models import DownloadToken, Movies, SentFile

logger = logging.getLogger(__name__)


# ❌ REMOVED: The delete_message_job function (now handled by a Cron Job)


async def handle_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command with token parameter"""
    logger.info(f"📨 Received /start from user {update.effective_user.id}")
    
    if not context.args:
        await update.message.reply_text(
            "🎬 Welcome to BollyFun!\n\n"
            "Get your download link from the website.\n\n"
            "⚠️ Files auto-delete after 24 hours."
        )
        return

    token_str = context.args[0]
    logger.info(f"🔑 Token: {token_str}")

    try:
        token = await sync_to_async(DownloadToken.objects.get)(token=token_str)
        movie_title = await sync_to_async(lambda: token.movie.title if token.movie else "Unknown")()
        logger.info(f"✅ Found: {movie_title}, {token.quality}")
    except DownloadToken.DoesNotExist:
        await update.message.reply_text("❌ Invalid or expired link.")
        return
    except Exception as e:
        logger.error(f"❌ Error fetching token: {e}")
        await update.message.reply_text("❌ An error occurred.")
        return

    if not token.is_valid():
        await sync_to_async(token.delete)()
        await update.message.reply_text("⏰ Link expired. Get a new one.")
        return

    movie = await sync_to_async(lambda: token.movie)()
    if not movie:
        await sync_to_async(token.delete)()
        await update.message.reply_text("❌ Invalid token.")
        return
    
    quality = token.quality
    file_id = await sync_to_async(
        lambda: movie.SD_telegram_file_id if quality == "SD" else movie.HD_telegram_file_id
    )()
    
    if not file_id:
        await sync_to_async(token.delete)()
        await update.message.reply_text(f"❌ File not found.")
        return

    processing_msg = await update.message.reply_text("⏳ Sending file...")

    try:
        movie_title = await sync_to_async(lambda: movie.title)()
        
        sent_message = await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=file_id,
            caption=f"🎬 **{movie_title}** ({quality})\n\n⚠️ Auto-deletes in 24h"
        )
        
        await processing_msg.delete()
        await update.message.reply_text(
            f"✅ **{quality}** for **{movie_title}** sent!\n\n"
            f"⏰ The server cleanup job is tracking this message for auto-deletion after 24 hours.",
            parse_mode="Markdown"
        )
        
        # ❌ REMOVED: context.job_queue.run_once(...)
        
        # This database entry is now the sole source of truth for the Cron Job.
        await sync_to_async(SentFile.objects.create)(
            chat_id=update.effective_chat.id,
            message_id=sent_message.message_id,
            movie=movie,
            quality=quality,
            delete_at=timezone.now() + timedelta(hours=24) 
        )
        
        await sync_to_async(token.delete)()
        logger.info("✅ File sent successfully and deletion scheduled via DB record.")
    
    except Exception as e:
        # If an error occurs during sending or DB creation, clean up the processing message
        try:
            await processing_msg.delete()
        except:
            pass # Ignore if it's already gone
            
        await update.message.reply_text("❌ Error sending file.")
        logger.error(f"Error sending file in handler: {e}")