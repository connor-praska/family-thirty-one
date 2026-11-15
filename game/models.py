from django.db import models


class Room(models.Model):
    code = models.CharField(max_length=8, unique=True)
    data = models.JSONField(default=dict)
    version = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class RoomMessage(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='messages')
    kind = models.CharField(max_length=8, default='chat')
    author = models.CharField(max_length=24)
    player_id = models.CharField(max_length=64, blank=True)
    text = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)
