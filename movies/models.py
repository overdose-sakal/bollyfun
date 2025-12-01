# movies/models.py
from django.db import models
from autoslug import AutoSlugField
import uuid
from datetime import timedelta
from django.utils import timezone



# Create your models here.
class Movies(models.Model):
    title = models.CharField(max_length=100)
    CATEGORY_CHOICES = [
        ('movies', 'Movies'),
        ('tv', 'TV Shows'),
        ('anime', 'Anime'),
    ]
    description = models.TextField(blank=True)
    type = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='movies'
    )
    upload_date = models.DateField(auto_now_add=True)
    size_mb = models.CharField(max_length=20)
    SD_format = models.BooleanField(null=True)
    HD_format = models.BooleanField(null=True)
    dp = models.URLField(max_length=500, null=False, blank=False) #display picture
    screenshot1 = models.URLField(max_length=500)
    screenshot2 = models.URLField(max_length=500)
    created_at = models.DateField(auto_now_add=True)


    

    #telegram links
    SD_telegram_file_id = models.CharField(max_length=500, blank=True, null=True) # Max length increased
    HD_telegram_file_id = models.CharField(max_length=500, blank=True, null=True) # Max length increased

    #message id (CRUCIAL for forwarding)
    SD_message_id = models.BigIntegerField(blank=True, null=True)
    HD_message_id = models.BigIntegerField(blank=True, null=True)

    SD_link = models.URLField(max_length=500, blank=True, null=True)
    HD_link = models.URLField(max_length=500, blank=True, null=True)

    slug = AutoSlugField(populate_from='title', unique=True, max_length=255)


    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
    
    def get_file_url(self):
        # Keeping for compatibility
        if self.SD_format and self.HD_format:
            return self.SD_link and self.HD_link
        
        elif self.SD_format:
            return self.SD_format
        
        elif self.HD_link:
            return self.HD_format


# --- DOWNLOAD TOKEN MODEL (UPDATED) ---
class DownloadToken(models.Model):
    """
    Stores a temporary token, tied to a file ID, with an expiration time.
    """
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    # New fields to properly link the token for lookup
    movie = models.ForeignKey(Movies, on_delete=models.CASCADE, null=True, blank=True) # <<< NEW
    quality = models.CharField(max_length=5, null=True, blank=True) # 'SD' or 'HD' <<< NEW
    
    file_id = models.CharField(max_length=500) 
    expires_at = models.DateTimeField()

    def save(self, *args, **kwargs):
        # Set expiration time to 1 hour (3600 seconds) from creation
        if not self.id and not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=1)
        super().save(*args, **kwargs)

    def is_valid(self):
        """Check if the token has expired."""
        return timezone.now() < self.expires_at

    def __str__(self):
        return f"Token {self.token} ({self.movie.title} - {self.quality}) (Expires: {self.expires_at.strftime('%Y-%m-%d %H:%M')})"


# Add this to the end of movies/models.py

class SentFile(models.Model):
    """
    Tracks files sent to users for auto-deletion after 24 hours
    """
    chat_id = models.BigIntegerField()
    message_id = models.BigIntegerField()
    movie = models.ForeignKey(Movies, on_delete=models.CASCADE)
    quality = models.CharField(max_length=5)  # 'SD' or 'HD'
    sent_at = models.DateTimeField(auto_now_add=True)
    delete_at = models.DateTimeField()
    
    class Meta:
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['delete_at']),
            models.Index(fields=['chat_id', 'message_id']),
        ]
    
    def __str__(self):
        return f"{self.movie.title} ({self.quality}) sent to {self.chat_id} - deletes at {self.delete_at}"