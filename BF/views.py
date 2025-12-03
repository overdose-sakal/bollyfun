# BF/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden, HttpResponse, Http404
from django.urls import reverse
from django.conf import settings
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from urllib.parse import quote  

# Import necessary third-party libraries
import requests 

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

# Import models and utilities
from movies.models import Movies, DownloadToken
from movies.telegram_utils import TelegramFileManager
from movies.serializers import MovieSerializer

import json
import logging
from telegram import Update
from telegram.ext import Application
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)

# Simple bot initialization for webhook
telegram_app = None

def get_telegram_app():
    """Lazy initialization of telegram app"""
    global telegram_app
    if telegram_app is None:
        # NOTE: Using getattr here is also safer, but assuming settings.TELEGRAM_BOT_TOKEN is present
        telegram_app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).updater(None).build()
        
        # Import and register handlers
        from telegram.ext import CommandHandler
        from movies.bot_handlers import handle_start_command
        telegram_app.add_handler(CommandHandler("start", handle_start_command))
        
        logger.info("✅ Telegram app initialized")
    
    return telegram_app


# --- SHRINKURL API CALL FUNCTION (ROBUST) ---
def shorten_url_shrinkearn(long_url):
    """
    Calls the ShrinkEarn API to shorten the URL.
    Returns the shortened URL or the original URL on failure.
    """
    # 1. Safely retrieve API key to prevent 500 error if it's missing
    api_key = getattr(settings, 'SHRINK_EARN_API_KEY', None)
    
    if not api_key:
        logger.error("❌ SHRINK_EARN_API_KEY is not set in settings. Skipping shortening.")
        return long_url
    
    # Correct API endpoint format for ShrinkEarn
    api_url = "https://shrinkearn.com/api"
    
    params = {
        'api': api_key,
        'url': long_url,
        'alias': '' 
    }
    
    try:
        logger.info(f"🔗 Attempting to shorten URL: {long_url}")
        response = requests.get(api_url, params=params, timeout=10)
        
        # Log response for debugging on Render
        logger.info(f"ShrinkEarn API Response Status: {response.status_code}")
        logger.info(f"ShrinkEarn API Response: {response.text}") 
        
        response.raise_for_status() # Raises an exception for HTTP error codes
        data = response.json()
        
        if data.get('status') == 'success' and data.get('shortenedUrl'):
            short_url = data['shortenedUrl']
            logger.info(f"✅ URL shortened successfully: {short_url}")
            return short_url
        else:
            # This handles API errors (e.g., bad API key)
            logger.warning(f"❌ ShrinkEarn API failed or unexpected response: {data}")
            return long_url
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error communicating with ShrinkEarn API: {e}")
        return long_url
    except json.JSONDecodeError:
        logger.error("❌ ShrinkEarn API returned non-JSON response.")
        return long_url


# --- CORE VIEWS ---

def Home(request):
    query = request.GET.get("q", "")
    if query:
        all_movies = Movies.objects.filter(title__icontains=query)
    else:
        all_movies = Movies.objects.all().order_by('-upload_date')
    
    paginator = Paginator(all_movies, 12)
    page = request.GET.get('page')
    movies_page = paginator.get_page(page)

    return render(request, "index.html", {
        "movies": movies_page,
        "query": query,
    })


def Movie(request, slug):
    movie = get_object_or_404(Movies, slug=slug)
    
    # Pass the download status to the template
    sd_download_url = bool(movie.SD_telegram_file_id)
    hd_download_url = bool(movie.HD_telegram_file_id)
    
    return render(request, "movie_detail.html", {
        "movie": movie,
        "sd_download_url": sd_download_url,
        "hd_download_url": hd_download_url,
    })


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
        "query": query,
        "category": category,
    })


# --- DOWNLOAD TOKEN VIEWS ---

def download_token_view(request, quality, slug):
    """
    Generates a token, shortens the Telegram deep link, and redirects the user
    to the SHORTENED AD URL.
    """
    movie = get_object_or_404(Movies, slug=slug)
    quality = quality.upper()

    # 1. Check file availability
    file_id = None
    if quality == 'SD' and movie.SD_telegram_file_id:
        file_id = movie.SD_telegram_file_id
    elif quality == 'HD' and movie.HD_telegram_file_id:
        file_id = movie.HD_telegram_file_id
    else:
        logger.warning(f"Download link requested for {slug} ({quality}) but file_id is missing.")
        return HttpResponseForbidden("Download link is not available for this quality.")

    # 2. Create the Download Token
    token_instance = DownloadToken.objects.create(
        movie=movie, 
        quality=quality,
        file_id=file_id,
    )

    # 3. Construct the Telegram deep link (the link to be monetized)
    # Safely retrieve the bot username
    bot_username = getattr(settings, 'TELEGRAM_BOT_USERNAME', 'YourBotUsername_placeholder') 
    
    # This URL goes to your token validation view
    redirect_back_url = f"{settings.BASE_DOMAIN}/dl/{token_instance.token}/"

    # ShrinkEarn will point to this
    short_url = shorten_url_shrinkearn(redirect_back_url)

    return redirect(short_url)


def download_file_redirect(request, token):
    """
    Called after the user completes the ShrinkEarn ad.
    It verifies the token and redirects the user to the file-ready page.
    """
    try:
        token_instance = get_object_or_404(DownloadToken, token=token)
    except Http404:
        # Handle case where token is invalid or expired (Django will auto-return 404)
        return render(request, 'download_error.html', {'error_message': 'Invalid or expired download link. Please get a new link from the movie page.'}, status=410)

    # Check if the token is still valid (not expired)
    if not token_instance.is_valid():
        token_instance.delete() # Clean up expired token
        return render(request, 'download_error.html', {'error_message': 'Your download link has expired. Please get a new link from the movie page.'}, status=410)
    
    # The new final destination page path
    # We pass the movie title and the token via query parameters for the final download page
    # The 'download.html' template handles building the final /start link to the bot
    # final_download_page_url = f"/download.html?token={token_instance.token}&title={quote(token_instance.movie.title)}&quality={token_instance.quality}"


    return redirect(f"/download.html?token={token_instance.token}&title={quote(token_instance.movie.title)}&quality={token_instance.quality}")



def download_page_view(request):
    """
    Renders the final download page (download.html).
    The Vue app in the template handles building the final Telegram deep link.
    """
    # The token and movie title are passed as query params
    token = request.GET.get('token')
    movie_title = request.GET.get('title')
    quality = request.GET.get('quality')
    
    if not token or not movie_title or not quality:
        # Should not happen if previous view worked, but safety first
        return render(request, 'download_error.html', {'error_message': 'Missing download parameters.'}, status=400)
    
    # Safely retrieve the bot username
    bot_username = getattr(settings, 'TELEGRAM_BOT_USERNAME', 'YourBotUsername_placeholder')
    
    context = {
        'token': token,
        'movie_title': movie_title,
        'quality': quality,
        'bot_username': bot_username,
        'telegram_deep_link': f"https://t.me/{bot_username}?start={token}",
    }
    
    return render(request, 'download.html', context)


# --- TELEGRAM WEBHOOK VIEW ---

@csrf_exempt
async def telegram_webhook_view(request):
    """
    Handles incoming Telegram updates via webhook.
    """
    if request.method == "POST":
        try:
            update_data = json.loads(request.body.decode("utf-8"))
            update = Update.de_json(update_data, get_telegram_app().bot)
            
            # Process the update asynchronously
            await get_telegram_app().process_update(update)
            
            return HttpResponse(status=200)

        except Exception as e:
            logger.error(f"Error processing Telegram webhook: {e}")
            return HttpResponse(status=500)
    
    return HttpResponseForbidden('GET requests are not allowed')


# --- REST API VIEWS ---

class MovieViewSet(viewsets.ModelViewSet):
    queryset = Movies.objects.all().order_by('-upload_date')
    serializer_class = MovieSerializer
    
    # OPTIONAL: You can add custom actions here if needed
    @action(detail=False, methods=['get'], url_path='search')
    def search_movies(self, request):
        query = request.query_params.get('q', '')
        if query:
            queryset = self.queryset.filter(title__icontains=query)
        else:
            queryset = self.queryset.none() # Return empty if no query
            
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)