#movies/serializers.py

from rest_framework import serializers
from .models import Movies, DownloadToken
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

class MovieSerializer(serializers.ModelSerializer):
    sd_download_url = serializers.SerializerMethodField()
    hd_download_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Movies
        fields = [
            'id', 'title', 'description', 'upload_date', 'size_mb',
            'SD_format', 'HD_format', 'dp', 'screenshot1', 'screenshot2',
            'slug', 'sd_download_url', 'hd_download_url' # Renamed field
        ]
    
    def _generate_token_url(self, obj, file_id, quality):
        """Creates a token and returns the download URL."""
        if not file_id:
            return None
        
        # 1. Clear old, expired tokens to prevent database clutter (optional but good practice)
        # We only clear old tokens associated with this movie/quality/file_id
        expiration_threshold = timezone.now() - timedelta(minutes=10) # Clear tokens older than 10 minutes that should've been used
        DownloadToken.objects.filter(
            movie=obj,
            quality=quality,
            expires_at__lt=timezone.now()
        ).delete()
        
        # 2. Check for an existing valid token (optional but prevents unnecessary token creation)
        valid_token = DownloadToken.objects.filter(
            movie=obj,
            quality=quality,
            file_id=file_id,
            expires_at__gt=timezone.now()
        ).first()

        if valid_token:
            token = valid_token.token
        else:
            # 3. Create a new token (expires in 1 hour by default in model save method)
            token_instance = DownloadToken.objects.create(
                movie=obj,
                file_id=file_id,
                quality=quality,
            )
            token = token_instance.token

        # 4. Return the URL pointing to the new token validation view
        request = self.context.get('request')
        if request:
             return request.build_absolute_uri(reverse('validate_download_token', kwargs={'token': token}))
        return f'/download/{token}/' # Fallback URL
    
    def get_sd_download_url(self, obj):
        """Generate a temporary SD download link URL"""
        return self._generate_token_url(obj, obj.SD_telegram_file_id, 'SD')
    
    def get_hd_download_url(self, obj):
        """Generate a temporary HD download link URL"""
        return self._generate_token_url(obj, obj.HD_telegram_file_id, 'HD')