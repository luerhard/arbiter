from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserChangeForm as OrigUserChangeForm
from django.contrib.auth.forms import UserCreationForm as OrigUserCreationForm


User = get_user_model()


class UserCreationForm(OrigUserCreationForm):
    """
    Specify the user model created while adding a user
    on the admin page.
    """

    class Meta:
        model = User
        fields = (
            "username",
            "password",
            "is_staff",
            "is_active",
            "groups",
            "user_permissions",
        )


class UserChangeForm(OrigUserChangeForm):
    """
    Specify the user model edited while editing a user on the
    admin page.
    """

    class Meta:
        model = User
        fields = (
            "username",
            "password",
            "is_staff",
            "is_active",
            "groups",
            "user_permissions",
        )


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]
