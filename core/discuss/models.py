from django.contrib.auth import get_user_model
from django.db import models

from data.models import Example

User = get_user_model()


# Create your models here.
class Room(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)


class Message(models.Model):
    # TODO: user is currently not a ForeignKey to User, cuz we want system messages.
    # How should we handle that with ForeignKeys? Do we even need keys
    # user = models.ForeignKey(User, on_delete=models.DO_NOTHING)
    room = models.ForeignKey(Room, related_name="messages", on_delete=models.CASCADE)
    user = models.CharField(max_length=64)
    example = models.ForeignKey(Example, related_name="messages", on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"[{self.user.username : self.created_at}] {self.message}"
