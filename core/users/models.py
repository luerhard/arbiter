from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, username, password, **extra_fields):
        user = self.model(
            username=username,
            **extra_fields,
        )

        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, username, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        return self.create_user(username, password, **extra_fields)


class User(AbstractUser):
    email = models.EmailField(verbose_name="Email Adress", blank=True, null=True)

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = []

    objects = UserManager()  # type: ignore

    def __str__(self) -> str:
        return self.username
