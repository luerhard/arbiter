"""Opening a batch's annotation, discussion or expert page marks the user's notifications of
that batch read: the toast about the phase change has done its job, however the user got
there (dashboard, project page, done page, the toast itself)."""

from django.urls import reverse
from notifications.models import Notification
import pytest

from data.models import ExampleAssignment
from projects.models import Batch
from projects.models import BatchPhase


def _unread(user, batch):
    return Notification.objects.filter(user=user, batch=batch, read_at__isnull=True).count()


@pytest.mark.django_db
class TestMarkReadOnVisit:
    def test_annotation_page(self, client, project_annotation):
        a1, a2 = project_annotation["annotators"]
        batch = project_annotation["batch"]
        other_batch = Batch.objects.create(
            project=project_annotation["project"],
            current_phase=BatchPhase.SETUP,
        )
        Notification.objects.create(user=a1, batch=other_batch, message="Another batch")
        assert _unread(a1, batch) == 1
        client.force_login(a1)

        response = client.get(reverse("annotate-batch", args=(batch.id,)), follow=True)

        assert response.status_code == 200
        assert _unread(a1, batch) == 0
        assert _unread(a1, other_batch) == 1  # only the batch that was opened
        assert _unread(a2, batch) == 1  # only the user who opened it

    def test_moving_between_samples_does_not_write(self, client, project_annotation):
        a1 = project_annotation["annotators"][0]
        batch = project_annotation["batch"]
        assignment = ExampleAssignment.objects.get(user=a1, phase=BatchPhase.ANNOTATION)
        client.force_login(a1)

        client.get(
            reverse("annotate-assignment", args=(batch.id, assignment.id)),
            HTTP_HX_REQUEST="true",
        )

        assert _unread(a1, batch) == 1

    def test_discussion_page(self, client, project_discussion):
        a1 = project_discussion["annotators"][0]
        batch = project_discussion["batch"]
        client.force_login(a1)

        assert client.get(reverse("discuss-batch", args=(batch.id,))).status_code == 200

        assert _unread(a1, batch) == 0
        assert _unread(project_discussion["expert"], batch) > 0

    def test_done_page_leaves_the_discussion_toast(self, client, project_discussion):
        # the done page only links to the discussion (#199); the toast goes once it is opened
        a1 = project_discussion["annotators"][0]
        batch = project_discussion["batch"]
        client.force_login(a1)

        client.get(reverse("annotate-done", args=(batch.id,)))

        assert _unread(a1, batch) > 0

    def test_discussion_page_of_a_batch_not_in_discussion(self, client, project_annotation):
        a1 = project_annotation["annotators"][0]
        batch = project_annotation["batch"]
        client.force_login(a1)

        response = client.get(reverse("discuss-batch", args=(batch.id,)))

        assert response.status_code == 302
        assert _unread(a1, batch) == 1

    def test_expert_page(self, client, project_expert):
        expert = project_expert["expert"]
        batch = project_expert["batch"]
        client.force_login(expert)

        response = client.get(reverse("expert-batch", args=(batch.id,)), follow=True)

        assert response.status_code == 200
        assert _unread(expert, batch) == 0
        for annotator in project_expert["annotators"]:
            assert _unread(annotator, batch) > 0
