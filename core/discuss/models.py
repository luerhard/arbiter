from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


# Create your models here.


class Room(models.Model):
    n_online = models.SmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class DiscussMessage(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"[{self.user.username : self.created_at}] {self.message}"
