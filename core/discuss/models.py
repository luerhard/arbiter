from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


# Create your models here.
class DiscussMessage(models.Model):
    message = models.TextField()
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"[{self.user.username : self.created_at}] {self.message}"
