from django.urls import reverse
import pytest

from core.models import SiteSettings
from users.models import User


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("page", "who", "status"),
    [
        ("login", "anonymous", 200),
        ("user-profile", "anonymous", 302),
        ("user-profile", "annotator", 200),
    ],
)
def test_access(get_as, project_annotation, page, who, status):
    assert get_as(reverse(page), who, project_annotation).status_code == status


@pytest.mark.django_db
def test_logout_redirects_to_login(client):
    url = reverse("logout")
    login = client.login(username="annotator1", password="123")
    assert login == True
    req = client.get(url)
    assert req.status_code == 302
    assert req.url == reverse("login")


@pytest.fixture
def registration_open(db):  # noqa: ARG001, PT004
    SiteSettings.objects.update_or_create(pk=1, defaults={"allow_registration": True})


REGISTRATION = {
    "username": "newcomer",
    "email": "",
    "password1": "a-long-password-77",
    "password2": "a-long-password-77",
}


@pytest.mark.django_db
class TestClosedRegistration:
    def test_is_the_default(self, client):
        assert SiteSettings.load().allow_registration is False
        assert client.get(reverse("register")).status_code == 404
        assert client.post(reverse("register"), REGISTRATION).status_code == 404
        assert not User.objects.filter(username="newcomer").exists()
        assert reverse("register") not in client.get(reverse("login")).content.decode()


@pytest.mark.django_db
@pytest.mark.usefixtures("registration_open")
class TestOpenRegistration:
    def test_login_page_links_to_it_when_open(self, client):
        assert reverse("register") in client.get(reverse("login")).content.decode()

    def test_creates_a_plain_user_and_signs_in(self, client):
        response = client.post(reverse("register"), REGISTRATION)

        assert response.status_code == 302
        assert response.url == reverse("home")
        user = User.objects.get(username="newcomer")
        assert not user.is_staff
        assert not user.is_superuser
        assert not user.groups.exists()
        assert client.get(reverse("home")).context["user"] == user

    def test_rejects_a_taken_username_in_other_case(self, client):
        response = client.post(reverse("register"), {**REGISTRATION, "username": "Annotator1"})

        assert response.status_code == 200
        assert response.context["form"].errors["username"]
        assert not User.objects.filter(username="Annotator1").exists()

    def test_rejects_mismatched_passwords(self, client):
        response = client.post(
            reverse("register"), {**REGISTRATION, "password2": "something-else-77"}
        )

        assert response.status_code == 200
        assert response.context["form"].errors["password2"]
        assert not User.objects.filter(username="newcomer").exists()

    def test_signed_in_users_go_home(self, client):
        client.login(username="annotator1", password="123")
        response = client.get(reverse("register"))
        assert response.status_code == 302
        assert response.url == reverse("home")


@pytest.mark.django_db
class TestSiteSettingsAdmin:
    def test_list_goes_straight_to_the_one_row(self, client):
        client.login(username="admin", password="123")
        response = client.get(reverse("admin:core_sitesettings_changelist"))
        assert response.status_code == 302
        assert response.url == reverse("admin:core_sitesettings_change", args=(1,))
        assert client.get(response.url).status_code == 200

    def test_flag_can_be_switched_on(self, client):
        client.login(username="admin", password="123")
        url = reverse("admin:core_sitesettings_change", args=(SiteSettings.load().pk,))
        client.post(url, {"allow_registration": "on"})
        assert SiteSettings.load().allow_registration is True

    def test_saving_keeps_one_row(self):
        SiteSettings(allow_registration=True).save()
        assert SiteSettings.objects.count() == 1
        assert SiteSettings.load().allow_registration is True

    def test_user_admin_shows_email(self, client):
        client.login(username="admin", password="123")
        user = User.objects.get(username="annotator1")
        response = client.get(reverse("admin:users_user_change", args=(user.pk,)))
        assert response.status_code == 200
        assert 'name="email"' in response.content.decode()


@pytest.fixture
def member(client):
    user = User.objects.create_user("profile_owner", password="old-password-77")
    client.force_login(user)
    return user


@pytest.mark.django_db
class TestProfile:
    def test_saves_name_and_email(self, client, member):
        response = client.post(
            reverse("user-profile"),
            {
                "form": "profile",
                "first_name": "Ada",
                "last_name": "Lovelace",
                "email": "ada@example.org",
            },
        )

        assert response.status_code == 302
        member.refresh_from_db()
        assert (member.first_name, member.last_name, member.email) == (
            "Ada",
            "Lovelace",
            "ada@example.org",
        )
        assert member.username == "profile_owner"

    def test_ignores_the_username(self, client, member):
        client.post(reverse("user-profile"), {"form": "profile", "username": "someone_else"})
        member.refresh_from_db()
        assert member.username == "profile_owner"

    def test_rejects_an_invalid_email(self, client, member):
        response = client.post(
            reverse("user-profile"), {"form": "profile", "email": "not-an-email"}
        )

        assert response.status_code == 200
        assert response.context["profile_form"].errors["email"]
        member.refresh_from_db()
        assert not member.email

    def test_changes_the_password_and_stays_signed_in(self, client, member):
        response = client.post(
            reverse("user-profile"),
            {
                "form": "password",
                "old_password": "old-password-77",
                "new_password1": "new-password-88",
                "new_password2": "new-password-88",
            },
        )

        assert response.status_code == 302
        member.refresh_from_db()
        assert member.check_password("new-password-88")
        assert client.get(reverse("user-profile")).status_code == 200

    def test_password_needs_the_old_one(self, client, member):
        response = client.post(
            reverse("user-profile"),
            {
                "form": "password",
                "old_password": "wrong",
                "new_password1": "new-password-88",
                "new_password2": "new-password-88",
            },
        )

        assert response.status_code == 200
        assert response.context["password_form"].errors["old_password"]
        member.refresh_from_db()
        assert member.check_password("old-password-77")

    def test_page_does_not_contain_the_password_hash(self, client, member):
        assert member.password not in client.get(reverse("user-profile")).content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("who", ["anonymous", "annotator"])
def test_links_to_docs_and_source(client, who):
    if who == "annotator":
        client.login(username="annotator1", password="123")
        response = client.get(reverse("home"))
    else:
        response = client.get(reverse("login"))
    content = response.content.decode()
    assert "https://github.com/luerhard/arbiter" in content
    assert "https://luerhard.github.io/arbiter/" in content
