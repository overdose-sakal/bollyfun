# BF/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden, HttpResponse, Http404
from django.urls import reverse
from django.conf import settings
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from urllib.parse import quote  
import requests # <-- ENSURE THIS IMPORT IS PRESENT

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

# --- SHRINKURL API CALL FUNCTION (RESTORED) ---
def shorten_url_shrinkearn(long_url):
    """
    Calls the ShrinkEarn API to shorten the URL.
    Returns the shortened URL or the original URL on failure.
    """
    api_key = getattr(settings, 'SHRINK_EARN_API_KEY', None)
    
    if not api_key:
        logger.error("SHRINK_EARN_API_KEY is not set in settings.")
        return long_url
    
    api_url = f"https://shrinkearn.com/api" 
    
    params = {
        'api': api_key,
        'url': long_url
    }
    
    try:
        response = requests.get(api_url, params=params, timeout=5)
        response.raise_for_status() 
        data = response.json()
        
        if data.get('status') == 'success' and 'shortenedUrl' in data:
            short_url = data['shortenedUrl']
            logger.info(f"✅ URL shortened successfully: {short_url}")
            return short_url
        
        logger.warning(f"ShrinkEarn API failed or unexpected response structure: {data}")
        return long_url
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error communicating with ShrinkEarn API: {e}")
        return long_url
    except json.JSONDecodeError:
        logger.error("❌ ShrinkEarn API returned non-JSON response.")
        return long_url


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


def download_page_view(request):
    """
    Renders the final download page template (download.html).
    This is the secure destination after the ShrinkURL redirect.
    """
    return render(request, "download.html")


# BF/views.py (Replace the existing download_token_view with this)

def download_token_view(request, quality, slug):
    """
    Generates a token, SHORTENS THE DESTINATION URL, and redirects the user to the SHORTENED AD URL.
    """
    # ... (code to create/get token_instance remains the same) ...
    
    # 2. Construct the full final destination URL
    # FIX: Use getattr() to safely access BASE_DOMAIN, preventing a crash if it's missing.
    base_domain = getattr(settings, 'BASE_DOMAIN', request.build_absolute_uri('/').strip('/'))
    
    destination_path = reverse('validate_download_token', kwargs={'token': token_instance.token})
    destination_url = f"{base_domain}{destination_path}" 
    
    # 3. SHORTEN THE URL using the API
    short_url = shorten_url_shrinkearn(destination_url)

    # 4. Redirect the user to the SHORTENED URL
    return redirect(short_url)


def download_file_redirect(request, token):
    """
    This view validates the token (after the ShrinkURL ad) and 
    redirects the user to the final template page with parameters.
    """
    try:
        token_instance = get_object_or_404(DownloadToken, token=token)
    except Http404:
        return HttpResponseForbidden("Invalid download token.")

    if not token_instance.is_valid():
        token_instance.delete()
        return HttpResponseForbidden("Download link has expired. Please go back to the movie page to get a new link.")
    
    # 1. Prepare Title (e.g., "Movie Title (SD)")
    movie_title = f"{token_instance.movie.title} ({token_instance.quality})"
    
    # 2. Prepare Telegram Link
    bot_username = settings.TELEGRAM_BOT_USERNAME
    telegram_token_link = f"https://t.me/{bot_username}?start={token}"
    
    # 3. Get the URL for the final template view
    base_download_page_url = reverse("final_download_page") 
    
    # Encode title and the full Telegram link for safe URL passing
    encoded_title = quote(movie_title)
    encoded_link = quote(telegram_token_link)
    
    final_redirect_url = f"{base_download_page_url}?title={encoded_title}&link={encoded_link}"
    
    # Redirect to the template-served HTML page
    return redirect(final_redirect_url)


# ... (rest of the views: telegram_webhook_view, MovieViewSet, category_filter, etc.) ...


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

# NOTE: Keeping the structure of shorten_url_shrinkearn from your previous upload,
# but it is no longer called in the token generation flow, matching the desired
# flow where the final page is the ShrinkURL destination.

def shorten_url_shrinkearn(long_url):
    """
    Calls the ShrinkEarn API to shorten the URL.
    Returns the shortened URL or the original URL on failure.
    """
    # FIX: Use getattr() to safely access the key without crashing if it's missing
    api_key = getattr(settings, 'SHRINK_EARN_API_KEY', None)
    
    if not api_key:
        # This will now only log a warning and return the original URL, not crash.
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
        
        response.raise_for_status()
        data = response.json()
        
        if data.get('status') == 'success' and data.get('shortenedUrl'):
            short_url = data['shortenedUrl']
            logger.info(f"✅ URL shortened successfully: {short_url}")
            return short_url
        else:
            logger.warning(f"❌ ShrinkEarn API failed or unexpected response: {data}")
            return long_url
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error communicating with ShrinkEarn API: {e}")
        return long_url
    except json.JSONDecodeError:
        logger.error("❌ ShrinkEarn API returned non-JSON response.")
        return long_url