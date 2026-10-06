from django.db.models import Max
from django.urls import reverse
from django.utils import timezone
import pytest

from data.models import Example
from data.models import ExampleAssignment
from data.models import Label
from projects.models import BatchPhase
from projects.models.batch import BatchUser
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

        content = resp.content
        assert b'checked="False"' not in content
        assert b'disabled="False"' not in content
        assert b'checked="True"' not in content
        assert b'disabled="True"' not in content
        assert b':checked="detail.selected"' not in content

    def test_panel_label_checkboxes_use_form_field_name(self, client):
        # Regression guard (see the expert-phase bug): the rendered checkboxes
        # must POST under the name the form actually reads, otherwise label
        # selections are silently dropped.
        user = _first_annotator_user()
        batch_id = _first_annotation_batch_for_user(user)
        _ensure_batch_unfinished_for_user(batch_id, user)
        assignment = _first_assignment_for_user_in_batch(user, batch_id)

        login = client.login(username=user.username, password="123")
        assert login is True

        resp = client.get(reverse("annotate-assignment", args=(batch_id, assignment.id)))
        assert resp.status_code == 200
        html_name = resp.context["label_form"]["labels"].html_name
        content = resp.content.decode()
        labels = Label.objects.filter(project=assignment.example.batch.project)
        assert content.count(f'name="{html_name}"') >= labels.count()

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


@pytest.mark.django_db
class TestAnnotationDoneFinalize:
    def _annotate(self, data, label_for_a1, label_for_a2):
        a1, a2 = data["annotators"]
        example = data["example"]
        ExampleAssignment.objects.get(
            user=a1,
            example=example,
            phase=BatchPhase.ANNOTATION,
        ).set_user_annotations([label_for_a1.id])
        ExampleAssignment.objects.get(
            user=a2,
            example=example,
            phase=BatchPhase.ANNOTATION,
        ).set_user_annotations([label_for_a2.id])

    def test_finalize_ignored_when_not_done(self, client, project_annotation):
        a1 = project_annotation["annotators"][0]
        batch = project_annotation["batch"]

        client.login(username=a1.username, password="123")
        resp = client.post(reverse("annotate-done", args=(batch.id,)))

        assert resp.status_code == 302
        assert BatchUser.objects.get(batch=batch, user=a1).finalized_at is None
        batch.refresh_from_db()
        assert batch.current_phase == BatchPhase.ANNOTATION

    def test_partial_finalize_records_but_does_not_advance(self, client, project_annotation):
        data = project_annotation
        a1, a2 = data["annotators"]
        batch = data["batch"]
        label1, label2 = data["labels"]
        self._annotate(data, label1, label2)  # disagreement

        client.login(username=a1.username, password="123")
        resp = client.post(reverse("annotate-done", args=(batch.id,)))

        assert resp.status_code == 302
        assert BatchUser.objects.get(batch=batch, user=a1).finalized_at is not None
        assert BatchUser.objects.get(batch=batch, user=a2).finalized_at is None
        batch.refresh_from_db()
        assert batch.current_phase == BatchPhase.ANNOTATION

    def test_full_finalize_advances_to_discussion(self, client, project_annotation):
        data = project_annotation
        a1, a2 = data["annotators"]
        batch = data["batch"]
        label1, label2 = data["labels"]
        self._annotate(data, label1, label2)  # disagreement

        for annotator in (a1, a2):
            client.login(username=annotator.username, password="123")
            client.post(reverse("annotate-done", args=(batch.id,)))

        batch.refresh_from_db()
        assert batch.current_phase == BatchPhase.DISCUSSION


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

        self.url = reverse("annotate-assignment", args=(self.batch_id, self.assignment.id))

    def test_post_correct_labels_saves_and_advances(self, client):
        assert self.assignment.annotations.count() == 0
        labels = Label.objects.filter(project=self.assignment.example.batch.project)
        label_ids = list(labels.values_list("id", flat=True)[:2])
        assert label_ids

        resp = client.post(
            self.url,
            data={"assignment_id": self.assignment.id, "labels": label_ids},
            HTTP_HX_REQUEST="true",
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
        assert (
            reverse(
                "annotate-assignment",
                args=(next_assignment.example.batch_id, next_assignment.id),
            ).encode()
            in resp.content
        )

    def test_post_single_label_saves(self, client):
        assert self.assignment.annotations.count() == 0
        label = Label.objects.filter(project=self.assignment.example.batch.project).first()

        resp = client.post(
            self.url,
            data={"assignment_id": self.assignment.id, "labels": [label.id]},
            HTTP_HX_REQUEST="true",
        )
        assert resp.status_code == 200

        self.assignment.refresh_from_db()
        assert self.assignment.done is not None
        assert list(self.assignment.annotations.values_list("label_id", flat=True)) == [label.id]

    def test_post_no_labels_clears(self, client):
        labels = Label.objects.filter(project=self.assignment.example.batch.project)
        label_ids = list(labels.values_list("id", flat=True)[:1])
        self.assignment.set_user_annotations(label_ids=label_ids)
        assert self.assignment.annotations.count() == 1

        resp = client.post(
            self.url,
            data={"assignment_id": self.assignment.id},
            HTTP_HX_REQUEST="true",
        )
        assert resp.status_code == 200
        self.assignment.refresh_from_db()
        assert self.assignment.annotations.count() == 0

    def test_post_empty_labels_list_clears(self, client):
        labels = Label.objects.filter(project=self.assignment.example.batch.project)
        label_ids = list(labels.values_list("id", flat=True)[:1])
        self.assignment.set_user_annotations(label_ids=label_ids)
        assert self.assignment.annotations.count() == 1

        resp = client.post(
            self.url,
            data={"assignment_id": self.assignment.id, "labels": []},
            HTTP_HX_REQUEST="true",
        )
        assert resp.status_code == 200
        self.assignment.refresh_from_db()
        assert self.assignment.annotations.count() == 0

    def test_post_invalid_label_id_is_ignored(self, client):
        assert self.assignment.annotations.count() == 0
        resp = client.post(
            self.url,
            data={"assignment_id": self.assignment.id, "labels": [9999]},
            HTTP_HX_REQUEST="true",
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
            HTTP_HX_REQUEST="true",
        )
        assert resp.status_code == 200
        self.assignment.refresh_from_db()
        # Django's MultipleChoiceField treats any unknown value as invalid input,
        # so the form doesn't save partial results.
        assert self.assignment.annotations.count() == 0

    def test_post_non_integer_label_id_raises(self, client):
        resp = client.post(
            self.url,
            data={"assignment_id": self.assignment.id, "labels": ["not-a-number"]},
            HTTP_HX_REQUEST="true",
        )
        assert resp.status_code == 200
        self.assignment.refresh_from_db()
        assert self.assignment.annotations.count() == 0

    def test_post_to_non_annotation_phase_assignment_forbidden(self, client):
        # Regression: batch 1 of the populated DB also has DISCUSSION-phase
        # assignments for this user. The annotation view must never save into
        # them, otherwise annotation-phase input overwrites discussion labels.
        discussion_assignment = (
            ExampleAssignment.objects.filter(
                user=self.user,
                example__batch_id=self.batch_id,
                phase=BatchPhase.DISCUSSION,
            )
            .order_by("order")
            .first()
        )
        assert discussion_assignment is not None
        labels_before = sorted(
            discussion_assignment.annotations.values_list("label_id", flat=True),
        )

        label = Label.objects.filter(project=self.assignment.example.batch.project).first()
        url = reverse(
            "annotate-assignment",
            args=(self.batch_id, discussion_assignment.id),
        )
        resp = client.post(
            url,
            data={"assignment_id": discussion_assignment.id, "labels": [label.id]},
            HTTP_HX_REQUEST="true",
        )
        assert resp.status_code == 403

        discussion_assignment.refresh_from_db()
        assert (
            sorted(discussion_assignment.annotations.values_list("label_id", flat=True))
            == labels_before
        )

    def test_batch_entry_redirects_to_annotation_phase_assignment(self, client):
        # Regression: the entry redirect must pick the ANNOTATION-phase
        # assignment even though a DISCUSSION-phase assignment with the same
        # order exists in this batch.
        resp = client.get(reverse("annotate-batch", args=(self.batch_id,)))
        assert resp.status_code == 302
        assignment_id = int(resp.url.rstrip("/").split("/")[-1])
        assignment = ExampleAssignment.objects.get(id=assignment_id)
        assert assignment.phase == BatchPhase.ANNOTATION
        assert assignment.user == self.user

    def test_post_wrong_parameter_name_clears(self, client):
        labels = Label.objects.filter(project=self.assignment.example.batch.project)
        label_ids = list(labels.values_list("id", flat=True)[:1])
        self.assignment.set_user_annotations(label_ids=label_ids)
        assert self.assignment.annotations.count() == 1

        resp = client.post(
            self.url,
            data={"assignment_id": self.assignment.id, "wrong_labels": [1, 2]},
            HTTP_HX_REQUEST="true",
        )
        assert resp.status_code == 200
        self.assignment.refresh_from_db()
        assert self.assignment.annotations.count() == 0


@pytest.mark.django_db
class TestSkipAnnotatedToggle:
    @pytest.fixture(autouse=True)
    def _setup(self, client):
        self.user = _first_annotator_user()
        self.batch_id = _first_annotation_batch_for_user(self.user)
        _ensure_batch_unfinished_for_user(self.batch_id, self.user)

        self.assignments = list(
            ExampleAssignment.objects.filter(
                user=self.user,
                example__batch_id=self.batch_id,
                phase=BatchPhase.ANNOTATION,
            ).order_by("order"),
        )
        while len(self.assignments) < 3:
            _ensure_next_assignment_exists(self.assignments[-1])
            self.assignments = list(
                ExampleAssignment.objects.filter(
                    user=self.user,
                    example__batch_id=self.batch_id,
                    phase=BatchPhase.ANNOTATION,
                ).order_by("order"),
            )

        login = client.login(username=self.user.username, password="123")
        assert login is True

    def _url(self, assignment, qs=""):
        return reverse("annotate-assignment", args=(self.batch_id, assignment.id)) + qs

    def test_toggle_button_present_when_off(self, client):
        first = self.assignments[0]
        resp = client.get(self._url(first))
        assert resp.status_code == 200
        assert resp.context["skip_annotated"] is False
        assert b'id="skip-annotated-toggle"' in resp.content
        assert b'x-data="skipAnnotatedToggle()"' in resp.content
        assert b"Skip labeled" in resp.content

    def test_toggle_button_present_when_on(self, client):
        first = self.assignments[0]
        resp = client.get(self._url(first, "?skip_annotated=1"))
        assert resp.status_code == 200
        assert resp.context["skip_annotated"] is True
        assert b'id="skip-annotated-toggle"' in resp.content
        assert b"Skip labeled" in resp.content

    def test_get_redirects_to_next_unfinished_when_landing_on_done_with_skip(self, client):
        # Simulates the bug: user finished item 0, navigated back to it, then
        # toggled "Hide finished". Landing on a done assignment with skip on
        # should jump them to the next unfinished example.
        first, second = self.assignments[0], self.assignments[1]
        first.done = timezone.now()
        first.save()

        resp = client.get(self._url(first, "?skip_annotated=1"))
        assert resp.status_code == 302
        assert resp.url == self._url(second, "?skip_annotated=1")

    def test_get_with_skip_on_done_wraps_around_to_earlier_unfinished(self, client):
        # User toggled skip on while viewing the LAST assignment, which is done.
        # No unfinished after it, so wrap around to the first unfinished one.
        last = self.assignments[-1]
        first = self.assignments[0]
        for idx, a in enumerate(self.assignments):
            a.done = None if idx == 0 else timezone.now()
            a.save()

        resp = client.get(self._url(last, "?skip_annotated=1"))
        assert resp.status_code == 302
        assert resp.url == self._url(first, "?skip_annotated=1")

    def test_get_with_skip_on_done_redirects_done_when_nothing_unfinished(self, client):
        first = self.assignments[0]
        for a in self.assignments:
            a.done = timezone.now()
            a.save()

        resp = client.get(self._url(first, "?skip_annotated=1"))
        assert resp.status_code == 302
        assert resp.url == reverse("annotate-done", args=(self.batch_id,))

    def test_get_without_skip_renders_done_assignment(self, client):
        # Without skip on, viewing a done assignment is a valid review action and
        # should NOT redirect.
        first = self.assignments[0]
        first.done = timezone.now()
        first.save()

        resp = client.get(self._url(first))
        assert resp.status_code == 200
        assert resp.context["assignment_id"] == first.id

    def test_navigation_urls_carry_param_when_toggle_on(self, client):
        first = self.assignments[0]
        second = self.assignments[1]
        resp = client.get(self._url(first, "?skip_annotated=1"))
        assert resp.status_code == 200
        assert resp.context["next_url"] == self._url(second, "?skip_annotated=1")
        assert resp.context["post_url"] == self._url(first, "?skip_annotated=1")
        assert f'hx-post="{self._url(first, "?skip_annotated=1")}"'.encode() in resp.content

    def test_navigation_urls_have_no_param_when_toggle_off(self, client):
        first = self.assignments[0]
        second = self.assignments[1]
        resp = client.get(self._url(first))
        assert resp.status_code == 200
        assert resp.context["next_url"] == self._url(second)
        assert resp.context["post_url"] == self._url(first)

    def test_next_url_skips_annotated_examples_when_on(self, client):
        first, second, third = self.assignments[0], self.assignments[1], self.assignments[2]
        second.done = timezone.now()
        second.save()

        resp = client.get(self._url(first, "?skip_annotated=1"))
        assert resp.status_code == 200
        assert resp.context["next_url"] == self._url(third, "?skip_annotated=1")

    def test_next_url_does_not_skip_when_off(self, client):
        first, second = self.assignments[0], self.assignments[1]
        second.done = timezone.now()
        second.save()

        resp = client.get(self._url(first))
        assert resp.status_code == 200
        assert resp.context["next_url"] == self._url(second)

    def test_prev_url_skips_annotated_examples_when_on(self, client):
        first, second, third = self.assignments[0], self.assignments[1], self.assignments[2]
        second.done = timezone.now()
        second.save()

        resp = client.get(self._url(third, "?skip_annotated=1"))
        assert resp.status_code == 200
        assert resp.context["prev_url"] == self._url(first, "?skip_annotated=1")

    def test_post_with_skip_advances_and_pushes_url_with_param(self, client):
        first, second = self.assignments[0], self.assignments[1]
        labels = Label.objects.filter(project=first.example.batch.project)
        label_ids = list(labels.values_list("id", flat=True)[:1])

        resp = client.post(
            self._url(first, "?skip_annotated=1"),
            data={"labels": label_ids},
            HTTP_HX_REQUEST="true",
        )
        assert resp.status_code == 200
        assert resp.headers["HX-Push-Url"] == self._url(second, "?skip_annotated=1")

    def test_post_with_skip_wraps_around_to_earlier_unfinished(self, client):
        # Only the first and the second-to-last assignments stay unfinished. After the
        # user POSTs the second-to-last, there is nothing unfinished AFTER it, so the
        # view should wrap around to the first unfinished assignment in the batch.
        wrap_target_idx = 0
        post_idx = len(self.assignments) - 2
        for idx, a in enumerate(self.assignments):
            a.done = None if idx in {wrap_target_idx, post_idx} else timezone.now()
            a.save()

        wrap_target = self.assignments[wrap_target_idx]
        current = self.assignments[post_idx]
        labels = Label.objects.filter(project=current.example.batch.project)
        label_ids = list(labels.values_list("id", flat=True)[:1])

        resp = client.post(
            self._url(current, "?skip_annotated=1"),
            data={"labels": label_ids},
            HTTP_HX_REQUEST="true",
        )
        assert resp.status_code == 200
        assert resp.headers["HX-Push-Url"] == self._url(wrap_target, "?skip_annotated=1")

    def test_post_without_skip_does_not_wrap_and_redirects_done_when_complete(self, client):
        # All assignments done except the current one. A plain POST (no skip) should
        # finalize the batch and redirect to the done page rather than wrapping around.
        current = self.assignments[-1]
        for a in self.assignments:
            if a.id == current.id:
                a.done = None
            else:
                a.done = timezone.now()
            a.save()

        labels = Label.objects.filter(project=current.example.batch.project)
        label_ids = list(labels.values_list("id", flat=True)[:1])

        resp = client.post(
            self._url(current),
            data={"labels": label_ids},
            HTTP_HX_REQUEST="true",
        )
        assert resp.status_code == 302
        assert resp.url == reverse("annotate-done", args=(self.batch_id,))
