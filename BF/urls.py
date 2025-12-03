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
    # API
    path("movies/", include("movies.urls")),

    # Website pages
    path("", Home, name="home"), 
    path("admin/", admin.site.urls),
    path("movie/<slug:slug>/", Movie, name="movie_detail"), 
    path("category/<str:category>/", views.category_filter, name="category_filter"),

    # ShrinkEarn → TOKEN VALIDATION
    path("dl/<uuid:token>/", download_file_redirect, name="download_file_redirect"),

    # User clicked Download → Generate ShrinkEarn link
    path("download/<str:quality>/<slug:slug>/", download_token_view, name="download_token"),

    # Final destination → download.html
    path("download.html", download_page_view, name="download_page"),

    # Telegram webhook
    path("telegram/webhook/", telegram_webhook_view, name="telegram_webhook"),
]
