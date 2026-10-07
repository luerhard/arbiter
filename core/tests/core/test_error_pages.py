"""Refusals and errors show a page in the app's layout with a way back, not a blank page."""

import html

from django.test import RequestFactory
from django.urls import reverse
from django.views.defaults import server_error
import pytest

from data.models import ExampleAssignment
from projects.models import BatchPhase
from projects.models import ProjectRole
from projects.models import ProjectUser
from projects.models.batch import BatchUser


def _text(response):
    return " ".join(html.unescape(response.content.decode()).split())


@pytest.mark.django_db
def test_missing_project_role_shows_the_access_page(client, project_annotation):
    codebook = project_annotation["project"].codebook.get()
    client.login(username=project_annotation["annotators"][0].username, password="123")

    response = client.get(reverse("codebook-edit", args=[codebook.pk]))

    assert response.status_code == 403
    text = _text(response)
    assert "No access" in text
    assert "You don't have the role this page needs in this project." in text
    assert f'href="{reverse("home")}"' in response.content.decode()
    assert 'aria-label="Projects"' in text or "All projects" in text  # the app's sidebar


@pytest.mark.django_db
def test_batch_outsider_shows_the_access_page(client, django_user_model, project_annotation):
    outsider = django_user_model.objects.create_user(username="outsider", password="123")
    client.login(username=outsider.username, password="123")

    response = client.get(reverse("annotate-batch", args=[project_annotation["batch"].id]))

    assert response.status_code == 403
    assert "You are not part of this batch in the role this page needs." in _text(response)


@pytest.mark.django_db
def test_someone_elses_expert_case_shows_the_access_page(client, django_user_model, project_expert):
    batch = project_expert["batch"]
    case = ExampleAssignment.objects.filter(batch=batch, phase=BatchPhase.EXPERT).first()
    second_expert = django_user_model.objects.create_user(username="expert_two", password="123")
    ProjectUser.objects.create(
        project=batch.project, user=second_expert, default_role=ProjectRole.EXPERT
    )
    BatchUser.objects.create(batch=batch, user=second_expert, role=ProjectRole.EXPERT)
    client.login(username=second_expert.username, password="123")

    response = client.get(reverse("expert-assignment", args=[batch.id, case.id]))

    assert response.status_code == 403
    assert "This case is not assigned to you." in _text(response)


@pytest.mark.django_db
def test_unknown_page_shows_the_not_found_page(client, project_annotation):
    client.login(username=project_annotation["expert"].username, password="123")

    response = client.get("/this/does/not/exist")

    assert response.status_code == 404
    assert "Page not found" in _text(response)
    assert "All projects" in _text(response)


def test_server_error_page():
    response = server_error(RequestFactory().get("/"))

    assert response.status_code == 500
    text = _text(response)
    assert "Something went wrong on the server" in text
    assert 'href="/"' in text
