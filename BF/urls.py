# BF/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.contrib import admin
from . import views

# NEW: Import ALL necessary views from the project-level views.py
from .views import (
    MovieViewSet, 
    Home, 
    Movie, 
    download_token_view, 
    download_file_redirect, 
    telegram_webhook_view,
    download_page_view,
)

# router = DefaultRouter()
# router.register("movies", MovieViewSet, basename="movies")

urlpatterns = [
    # API Router path
    # NOTE: You previously had path("", include(router.urls)), which is generally bad
    # as it conflicts with the Home view. Using 'api/' prefix instead:
    path("movies/", include("movies.urls")),

    # Functional View paths (for the website pages)
    path("", Home, name="home"), 
    path('admin/', admin.site.urls),
    path("movie/<slug:slug>/", Movie, name="movie_detail"), 
    path("category/<str:category>/", views.category_filter, name="category_filter"),

    # --- TEMPORARY LINK SYSTEM PATHS (ORDER IS CRUCIAL) ---
    
    # 1. Token Validation (MUST be first)
    path("download/token/<uuid:token>/", download_file_redirect, name="validate_download_token"),
    
    # 2. Token Creation 
    path("download/<str:quality>/<slug:slug>/", download_token_view, name="generate_download_token"),


    path("download.html", download_page_view, name="final_download_page"),

    # Webhook endpoint
    path("telegram/webhook/", telegram_webhook_view, name="telegram_webhook"),
]