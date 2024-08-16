from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models


# Create your models here.


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

    objects = UserManager()

    @property
    def is_annotator(self):
        return "Annotator" in [g.name for g in self.groups.all()]

    @property
    def is_expert(self):
        return "Expert" in [g.name for g in self.groups.all()]

    @property
    def is_admin(self):
        return "Admin" in [g.name for g in self.groups.all()]

    def __str__(self) -> str:
        return self.username
