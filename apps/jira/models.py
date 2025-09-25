from django.db import models
from django.conf import settings


class AtlassianConnection(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="atlassian_connection")
    access_token = models.TextField(blank=True, default="")
    refresh_token = models.TextField(blank=True, default="")
    expires_at = models.DateTimeField(null=True, blank=True)
    scope = models.TextField(blank=True, default="")
    token_type = models.CharField(max_length=32, blank=True, default="")
    cloud_id = models.CharField(max_length=128, blank=True, default="")
    cloud_name = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"AtlassianConnection<{self.user}>"

# Create your models here.
