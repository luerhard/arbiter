import re

from django.db.models import Max
from django.urls import reverse
from django.utils import timezone
import pytest

from data.models import Example
from data.models import ExampleAssignment
from data.models import Label
from projects.models import BatchPhase
from users.models import User


def _first_annotator_user():
    return User.objects.filter(username="annotator1").get()


def _first_non_annotator_user():
    return User.objects.filter(username="annotator3").get()


def _first_annotation_batch_for_user(user):
    batch = (
        ExampleAssignment.objects.filter(user=user, phase=BatchPhase.ANNOTATION)
        .order_by("example__batch_id")
        .values_list("example__batch_id", flat=True)
        .first()
    )
    assert batch is not None
    return batch


def _ensure_batch_unfinished_for_user(batch_id, user):
    ExampleAssignment.objects.filter(
        example__batch_id=batch_id,
        user=user,
        phase=BatchPhase.ANNOTATION,
    ).update(done=None)


def _ensure_batch_finished_for_user(batch_id, user):
    ExampleAssignment.objects.filter(
        example__batch_id=batch_id,
        user=user,
        phase=BatchPhase.ANNOTATION,
    ).update(done=timezone.now())


def _first_assignment_for_user_in_batch(user, batch_id):
    assignment = (
        ExampleAssignment.objects.filter(
            user=user,
            example__batch_id=batch_id,
            phase=BatchPhase.ANNOTATION,
        )
        .order_by("order")
        .first()
    )
    assert assignment is not None
    return assignment


def _ensure_next_assignment_exists(assignment):
    if assignment.next() is not None:
        return

    batch = assignment.example.batch
    user = assignment.user
    max_order = ExampleAssignment.objects.filter(
        batch=batch,
        user=user,
        phase=assignment.phase,
    ).aggregate(max_order=Max("order"))["max_order"]
    next_order = (max_order or 0) + 1
    example = Example.objects.create(batch=batch, content=f"Example {next_order}")
    ExampleAssignment.objects.create(
        batch=batch,
        user=user,
        example=example,
        phase=assignment.phase,
        order=next_order,
    )


@pytest.mark.django_db
class TestAnnotateViews:
    def test_login_required(self, client):
        batch_id = _first_annotation_batch_for_user(_first_annotator_user())
        url = reverse("annotate-batch", args=(batch_id,))
        resp = client.get(url)
        assert resp.status_code == 302

    def test_annotator_can_open_annotation_page(self, client):
        user = _first_annotator_user()
        batch_id = _first_annotation_batch_for_user(user)
        _ensure_batch_unfinished_for_user(batch_id, user)

        login = client.login(username=user.username, password="123")
        assert login is True

        resp = client.get(reverse("annotate-batch", args=(batch_id,)))
        assert resp.status_code == 302
        assert (
            reverse(
                "annotate-assignment",
                args=(batch_id, _first_assignment_for_user_in_batch(user, batch_id).id),
            )
            in resp.url
        )

        # Follow redirect and verify we get a full page.
        page = client.get(resp.url)
        assert page.status_code == 200
        assert b'id="annotation-panel"' in page.content
        assert b'id="assignmentId"' in page.content

    def test_non_annotator_forbidden(self, client):
        user = _first_non_annotator_user()
        batch_id = _first_annotation_batch_for_user(_first_annotator_user())
        login = client.login(username=user.username, password="123")
        assert login is True

        resp = client.get(reverse("annotate-batch", args=(batch_id,)))
        assert resp.status_code == 403

    def test_assignment_in_url_loads_panel_and_labels(self, client):
        user = _first_annotator_user()
        batch_id = _first_annotation_batch_for_user(user)
        _ensure_batch_unfinished_for_user(batch_id, user)
        assignment = _first_assignment_for_user_in_batch(user, batch_id)

        login = client.login(username=user.username, password="123")
        assert login is True

        resp = client.get(reverse("annotate-assignment", args=(batch_id, assignment.id)))
        assert resp.status_code == 200
        assert resp.context is not None
        assert resp.context["assignment_id"] == assignment.id
        assert resp.context["label_form"].label_details

        labels = Label.objects.filter(project=assignment.example.batch.project)
        assert labels.exists()

    def test_hx_request_returns_panel_only(self, client):
        user = _first_annotator_user()
        batch_id = _first_annotation_batch_for_user(user)
        _ensure_batch_unfinished_for_user(batch_id, user)
        assignment = _first_assignment_for_user_in_batch(user, batch_id)

        login = client.login(username=user.username, password="123")
        assert login is True

        resp = client.get(
            reverse("annotate-assignment", args=(batch_id, assignment.id)),
            HTTP_HX_REQUEST="true",
        )
        assert resp.status_code == 200
        assert b'id="annotation-panel"' in resp.content
        assert b"<html" not in resp.content

    def test_finished_batch_redirects_to_done(self, client):
        user = _first_annotator_user()
        batch_id = _first_annotation_batch_for_user(user)
        _ensure_batch_finished_for_user(batch_id, user)

        login = client.login(username=user.username, password="123")
        assert login is True

        resp = client.get(reverse("annotate-batch", args=(batch_id,)))
        assert resp.status_code == 302
        assert resp.url == reverse("annotate-done", args=(batch_id,))


@pytest.mark.django_db
class TestEditAssignmentView:
    @pytest.fixture(autouse=True)
    def _setup(self, client):
        self.user = _first_annotator_user()
        self.batch_id = _first_annotation_batch_for_user(self.user)
        _ensure_batch_unfinished_for_user(self.batch_id, self.user)
        self.assignment = _first_assignment_for_user_in_batch(self.user, self.batch_id)
        _ensure_next_assignment_exists(self.assignment)

        login = client.login(username=self.user.username, password="123")
        assert login is True

        self.url = reverse("annotate-edit")

    def test_post_correct_labels_saves_and_advances(self, client):
        assert self.assignment.annotations.count() == 0
        labels = Label.objects.filter(project=self.assignment.example.batch.project)
        label_ids = list(labels.values_list("id", flat=True)[:2])
        assert label_ids

        resp = client.post(
            self.url,
            data={"assignment_id": self.assignment.id, "labels": label_ids},
        )
        assert resp.status_code == 200
        assert "HX-Push-Url" in resp.headers

        self.assignment.refresh_from_db()
        assert sorted(self.assignment.annotations.values_list("label_id", flat=True)) == sorted(
            label_ids,
        )

        next_assignment = self.assignment.next()
        assert next_assignment is not None
        assert resp.headers["HX-Push-Url"] == reverse(
            "annotate-assignment",
            args=(next_assignment.example.batch_id, next_assignment.id),
        )
        assert re.search(rb'value="%d"' % next_assignment.id, resp.content)

    def test_post_no_labels_clears(self, client):
        labels = Label.objects.filter(project=self.assignment.example.batch.project)
        label_ids = list(labels.values_list("id", flat=True)[:1])
        self.assignment.set_user_annotations(label_ids=label_ids)
        assert self.assignment.annotations.count() == 1

        resp = client.post(self.url, data={"assignment_id": self.assignment.id})
        assert resp.status_code == 200
        self.assignment.refresh_from_db()
        assert self.assignment.annotations.count() == 0

    def test_post_empty_labels_list_clears(self, client):
        labels = Label.objects.filter(project=self.assignment.example.batch.project)
        label_ids = list(labels.values_list("id", flat=True)[:1])
        self.assignment.set_user_annotations(label_ids=label_ids)
        assert self.assignment.annotations.count() == 1

        resp = client.post(self.url, data={"assignment_id": self.assignment.id, "labels": []})
        assert resp.status_code == 200
        self.assignment.refresh_from_db()
        assert self.assignment.annotations.count() == 0

    def test_post_invalid_label_id_is_ignored(self, client):
        assert self.assignment.annotations.count() == 0
        resp = client.post(
            self.url,
            data={"assignment_id": self.assignment.id, "labels": [9999]},
        )
        assert resp.status_code == 200
        self.assignment.refresh_from_db()
        assert self.assignment.annotations.count() == 0

    def test_post_mixed_valid_and_invalid_label_ids(self, client):
        labels = Label.objects.filter(project=self.assignment.example.batch.project)
        valid_label_id = labels.first().id
        resp = client.post(
            self.url,
            data={"assignment_id": self.assignment.id, "labels": [valid_label_id, 9999]},
        )
        assert resp.status_code == 200
        self.assignment.refresh_from_db()
        assert self.assignment.annotations.count() == 1
        assert self.assignment.annotations.first().label_id == valid_label_id

    def test_post_non_integer_label_id_raises(self, client):
        with pytest.raises(ValueError):  # noqa: PT011
            client.post(
                self.url,
                data={"assignment_id": self.assignment.id, "labels": ["not-a-number"]},
            )

    def test_post_wrong_parameter_name_clears(self, client):
        labels = Label.objects.filter(project=self.assignment.example.batch.project)
        label_ids = list(labels.values_list("id", flat=True)[:1])
        self.assignment.set_user_annotations(label_ids=label_ids)
        assert self.assignment.annotations.count() == 1

        resp = client.post(
            self.url,
            data={"assignment_id": self.assignment.id, "wrong_labels": [1, 2]},
        )
        assert resp.status_code == 200
        self.assignment.refresh_from_db()
        assert self.assignment.annotations.count() == 0
