from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AdminUserCreationForm
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm
from django.contrib.auth.forms import UserChangeForm as OrigUserChangeForm
from django.contrib.auth.forms import UserCreationForm as DjangoUserCreationForm
from django.contrib.auth.password_validation import password_validators_help_texts

User = get_user_model()


class UserCreationForm(AdminUserCreationForm):
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


class UserRegistrationForm(DjangoUserCreationForm):
    """Self-registration on the sign-in page. Accounts made here are plain users: no staff,
    no admin, no groups."""

    class Meta(DjangoUserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, autocomplete in (
            ("username", "username"),
            ("email", "email"),
            ("password1", "new-password"),
            ("password2", "new-password"),
        ):
            self.fields[name].widget.attrs.update({"class": "input", "autocomplete": autocomplete})
        self.fields["username"].widget.attrs["autofocus"] = True
        self.fields["email"].label = "Email"
        # Django's help text for it is an HTML list; the page shows plain text
        self.fields["password1"].help_text = " ".join(password_validators_help_texts())


class ProfileForm(forms.ModelForm):
    """What users change about themselves on the profile page."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")
        labels = {"email": "Email"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, autocomplete in (
            ("first_name", "given-name"),
            ("last_name", "family-name"),
            ("email", "email"),
        ):
            self.fields[name].widget.attrs.update({"class": "input", "autocomplete": autocomplete})


class PasswordChangeForm(DjangoPasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input"
        self.fields["old_password"].widget.attrs.pop("autofocus", None)
        # Django's help text for it is an HTML list; the page shows plain text
        self.fields["new_password1"].help_text = " ".join(password_validators_help_texts())
