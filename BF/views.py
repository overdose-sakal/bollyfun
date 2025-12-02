# BF/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden, HttpResponse, Http404
from django.urls import reverse
from django.conf import settings
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from movies.models import Movies, DownloadToken
from movies.telegram_utils import TelegramFileManager
from movies.serializers import MovieSerializer

import json
import logging
from telegram import Update
from telegram.ext import Application

logger = logging.getLogger(__name__)

# Simple bot initialization for webhook
telegram_app = None

def get_telegram_app():
    """Lazy initialization of telegram app"""
    global telegram_app
    if telegram_app is None:
        telegram_app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).updater(None).build()
        
        # Import and register handlers
        from telegram.ext import CommandHandler
        from movies.bot_handlers import handle_start_command
        telegram_app.add_handler(CommandHandler("start", handle_start_command))
        
        logger.info("✅ Telegram app initialized")
    
    return telegram_app


# --- VIEWS ---

def Home(request):
    query = request.GET.get("q", "")
    if query:
        all_movies = Movies.objects.filter(title__icontains=query)
    else:
        all_movies = Movies.objects.all()

    paginator = Paginator(all_movies, 12)
    page_number = request.GET.get('page')
    movies = paginator.get_page(page_number)

    return render(request, "index.html", {"movies": movies, "query": query})


def Movie(request, slug):
    movie = get_object_or_404(Movies, slug=slug)
    
    sd_url = None
    hd_url = None
    
    if movie.SD_telegram_file_id:
        sd_url = reverse('generate_download_token', kwargs={'quality': 'sd', 'slug': slug})
    
    if movie.HD_telegram_file_id:
        hd_url = reverse('generate_download_token', kwargs={'quality': 'hd', 'slug': slug})
    
    context = {
        'movie': movie,
        'sd_download_url': sd_url,
        'hd_download_url': hd_url,
    }
    
    return render(request, 'movie_detail.html', context)


def download_token_view(request, quality, slug):
    movie = get_object_or_404(Movies, slug=slug)
    quality = quality.upper()
    file_id = None

    if quality == 'SD' and movie.SD_telegram_file_id:
        file_id = movie.SD_telegram_file_id
    elif quality == 'HD' and movie.HD_telegram_file_id:
        file_id = movie.HD_telegram_file_id
    else:
        return HttpResponseForbidden("Download link is not available for this quality.")
    
    valid_token_instance = DownloadToken.objects.filter(
        movie=movie,
        quality=quality,
        expires_at__gt=timezone.now()
    ).first()

    if valid_token_instance:
        token = valid_token_instance.token
    else:
        token_instance = DownloadToken.objects.create(
            movie=movie,
            quality=quality,
            file_id=file_id,
        )
        token = token_instance.token

    return redirect(reverse('validate_download_token', kwargs={'token': token}))


def download_file_redirect(request, token):
    try:
        token_instance = get_object_or_404(DownloadToken, token=token)
    except Http404:
        return HttpResponseForbidden("Invalid download token.")

    if not token_instance.is_valid():
        token_instance.delete()
        return HttpResponseForbidden("Download link has expired. Please go back to the movie page to get a new link.")
    
    bot_username = settings.TELEGRAM_BOT_USERNAME
    telegram_redirect_url = f"https://t.me/{bot_username}?start={token}"
    
    return redirect(telegram_redirect_url)


@csrf_exempt
async def telegram_webhook_view(request):
    """Receives updates from Telegram via webhook"""
    if request.method == 'POST':
        try:
            update_data = json.loads(request.body.decode('utf-8'))
            logger.info(f"📨 Received webhook update")
            
            app = get_telegram_app()
            
            # Initialize if needed
            if not app._initialized:
                await app.initialize()
            
            # Convert to Update object
            update = Update.de_json(update_data, app.bot)
            
            # Process the update
            await app.process_update(update)
            
            return HttpResponse(status=200)
        
        except Exception as e:
            logger.error(f"❌ Webhook error: {str(e)}")
            import traceback
            traceback.print_exc()
            return HttpResponse(status=500)
    
    return HttpResponse("Telegram Webhook Active", status=200)


class MovieViewSet(viewsets.ModelViewSet):
    queryset = Movies.objects.all()
    serializer_class = MovieSerializer
    lookup_field = "slug"
    
    @action(detail=True, methods=['get'])
    def download_link(self, request, slug=None):
        movie = self.get_object()
        quality = request.query_params.get('quality', 'sd').lower()
        
        telegram = TelegramFileManager()
        
        if quality == 'sd' and movie.SD_telegram_file_id:
            download_url = telegram.get_file_url(movie.SD_telegram_file_id)
            if download_url:
                return Response({
                    'success': True,
                    'quality': 'SD',
                    'download_url': download_url,
                    'movie': movie.title
                })
        
        elif quality == 'hd' and movie.HD_telegram_file_id:
            download_url = telegram.get_file_url(movie.HD_telegram_file_id)
            if download_url:
                return Response({
                    'success': True,
                    'quality': 'HD',
                    'download_url': download_url,
                    'movie': movie.title
                })
        
        return Response({
            'success': False,
            'error': 'Download link not available'
        }, status=status.HTTP_404_NOT_FOUND)

    
def category_filter(request, category):
    query = request.GET.get("q", "")
    movies = Movies.objects.filter(type=category)

    if query:
        movies = movies.filter(title__icontains=query)

    paginator = Paginator(movies, 12)
    page = request.GET.get('page')
    movies_page = paginator.get_page(page)

    return render(request, "category.html", {
        "movies": movies_page,
        "category": category,
        "query": query
    })