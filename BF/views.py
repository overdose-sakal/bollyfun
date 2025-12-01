# BF/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden, HttpResponse, Http404
from django.urls import reverse
from django.conf import settings
from django.utils import timezone

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

# IMPORTANT: Import models and utilities from the 'movies' app
from movies.models import Movies, DownloadToken
from movies.telegram_utils import TelegramFileManager
from movies.serializers import MovieSerializer
from telegram.ext import CommandHandler


import json
from django.views.decorators.csrf import csrf_exempt
from telegram import Update
from telegram.ext import Application, ContextTypes
from asgiref.sync import async_to_sync
import logging


# --- EXISTING FUNCTIONAL VIEWS (Updated to generate token URLs) ---

def Home(request):
    query = request.GET.get("q", "")

    if query:
        all_movies = Movies.objects.filter(title__icontains=query)
    else:
        all_movies = Movies.objects.all()

    paginator = Paginator(all_movies, 12)
    page_number = request.GET.get('page')
    movies = paginator.get_page(page_number)

    return render(request, "index.html", {
        "movies": movies,
        "query": query
    })


def Movie(request, slug):
    """
    Handles the movie detail page. Generates the starting URL for token creation.
    """
    movie = get_object_or_404(Movies, slug=slug)
    
    sd_url = None
    hd_url = None
    
    # Generate the URL that points to the token generation view
    if movie.SD_telegram_file_id:
        sd_url = reverse('generate_download_token', kwargs={'quality': 'sd', 'slug': slug})
    
    if movie.HD_telegram_file_id:
        hd_url = reverse('generate_download_token', kwargs={'quality': 'hd', 'slug': slug})
    
    context = {
        'movie': movie,
        'sd_download_url': sd_url, # Renamed from sd_download_link to match HTML update
        'hd_download_url': hd_url, # Renamed from hd_download_link to match HTML update
    }
    
    return render(request, 'movie_detail.html', context)


# --- NEW DOWNLOAD FLOW VIEWS ---

def download_token_view(request, quality, slug):
    """
    Endpoint (1): Creates a new DownloadToken (valid for 1 hour) and redirects 
    to the token validation view.
    """
    movie = get_object_or_404(Movies, slug=slug)
    quality = quality.upper()
    file_id = None

    if quality == 'SD' and movie.SD_telegram_file_id:
        file_id = movie.SD_telegram_file_id
    elif quality == 'HD' and movie.HD_telegram_file_id:
        file_id = movie.HD_telegram_file_id
    else:
        return HttpResponseForbidden("Download link is not available for this quality.")
    
    # Check for an existing valid token (Prevents generating a new token on every refresh/click)
    # NOTE: Requires the updated DownloadToken model with 'movie' and 'quality' fields
    valid_token_instance = DownloadToken.objects.filter(
        movie=movie,
        quality=quality,
        expires_at__gt=timezone.now()
    ).first()

    if valid_token_instance:
        token = valid_token_instance.token
    else:
        # Create a new token (expiration set in models.py to 1 hour)
        token_instance = DownloadToken.objects.create(
            movie=movie,
            quality=quality,
            file_id=file_id,
        )
        token = token_instance.token

    # Redirect to the token validation view
    return redirect(reverse('validate_download_token', kwargs={'token': token}))


def download_file_redirect(request, token):
    """
    Endpoint (2): Validates the token and redirects the user 
    to the Telegram bot with the token payload.
    DON'T delete the token here - let the bot delete it after sending the file.
    """
    try:
        # 1. Retrieve the token object
        token_instance = get_object_or_404(DownloadToken, token=token)
    except Http404:
        return HttpResponseForbidden("Invalid download token.")

    # 2. Validate 1-hour expiration time
    if not token_instance.is_valid():
        token_instance.delete() # Clean up expired token
        return HttpResponseForbidden("Download link has expired. Please go back to the movie page to get a new link.")
    
    # 3. Generate the Telegram bot redirect link
    bot_username = settings.TELEGRAM_BOT_USERNAME
    
    # The crucial part: Redirecting the user to the bot with the token in the payload
    telegram_redirect_url = f"https://t.me/{bot_username}?start={token}"
    
    # 4. DON'T DELETE TOKEN HERE - The bot will delete it after successful delivery
    # token_instance.delete()  # ← REMOVE THIS LINE
    
    # 5. Redirect the user
    return redirect(telegram_redirect_url)

logger = logging.getLogger(__name__)

# Create the bot application (outside the view)
telegram_app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

# Import your start handler from the bot logic
from movies.bot_handlers import handle_start_command

# Register handlers
telegram_app.add_handler(CommandHandler("start", handle_start_command))

@csrf_exempt
async def telegram_webhook_view(request):
    """
    Receives updates from Telegram via webhook
    """
    if request.method == 'POST':
        try:
            # Parse the incoming update
            update_data = json.loads(request.body.decode('utf-8'))
            logger.info(f"Received webhook update: {update_data}")
            
            # Convert to Telegram Update object
            update = Update.de_json(update_data, telegram_app.bot)
            
            # Process the update
            await telegram_app.process_update(update)
            
            return HttpResponse(status=200)
        
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            import traceback
            traceback.print_exc()
            return HttpResponse(status=500)
    
    return HttpResponse("Telegram Webhook is Active", status=200)


# --- DRF VIEWS (MovieViewSet remains) ---

class MovieViewSet(viewsets.ModelViewSet):
    queryset = Movies.objects.all()
    serializer_class = MovieSerializer
    lookup_field = "slug"
    
    # Keeping the original download_link action for API usage, 
    # as it may be used by external services (using the get_file_url method).
    @action(detail=True, methods=['get'])
    def download_link(self, request, slug=None):
        """Original API endpoint."""
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
