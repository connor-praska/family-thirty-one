from django.db import models


class Room(models.Model):
    code = models.CharField(max_length=8, unique=True)
    data = models.JSONField(default=dict)
    version = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
