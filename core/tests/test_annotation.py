from django.urls import reverse
import pytest

from core.models import Project


pytestmark = pytest.mark.django_db

@pytest.fixture()
def client_a(client):
    client.login(username="annotator1")
    return client

@pytest.mark.usefixtures("_populate_db")
def test_testdata(db, django_user_model):
    users = django_user_model.objects.all()
    assert len(users) == 7
    assert len([1 for user in users for group in user.groups.all() if group.name == "Expert"]) == 3
    assert (
        len([1 for user in users for group in user.groups.all() if group.name == "Annotator"]) == 4
    )
    assert Project.objects.count() == 2

    project = Project.objects.filter(name="testproject1").get()
    batch = project.batches.first()
    sentences = batch.sentences.all()
    assert len(sentences) == 20

    project = Project.objects.filter(name="testproject2").get()
    assert len(project.batches.all()) == 2


def test_project_list_view_not_logged_in_redirect(client):
    url = reverse("list-projects")
    req = client.get(url)
    assert req.status_code == 302
    assert req.url == "/users/login?next=/projects/"


@pytest.mark.usefixtures("_populate_db")
def test_project_list_view(client, django_user_model):
    user = django_user_model.objects.filter(username="annotator1")
    assert user.count() == 1

    login = client.login(username="annotator1", password="123")
    assert login == True
    url = reverse("list-projects")
    req = client.get(url)
    assert req.status_code == 200
