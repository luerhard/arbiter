from django.urls import reverse
import pytest

from discuss import room_state
from discuss.models import Message
from discuss.models import Room
from projects.models import Batch


def _chat(batch_id, client):
    room = Room.objects.create(pk=batch_id)
    Message.objects.create(room=room, user="system", message="annotator1 is now connected.")
    client.set(f"room:{batch_id}", "{}")


@pytest.mark.django_db
class TestChatIsDeletedWithItsBatch:
    def test_batch_deletion(
        self, client, redis_client, project_annotation, django_capture_on_commit_callbacks
    ):
        batch = project_annotation["batch"]
        other = Batch.objects.exclude(pk=batch.pk).first()
        _chat(batch.pk, redis_client)
        _chat(other.pk, redis_client)
        client.login(username=project_annotation["expert"].username, password="123")

        with django_capture_on_commit_callbacks(execute=True):
            client.post(reverse("delete-batch", args=(batch.pk,)))

        assert not Room.objects.filter(pk=batch.pk).exists()
        assert not Message.objects.filter(room_id=batch.pk).exists()
        assert not redis_client.exists(f"room:{batch.pk}")
        assert Room.objects.filter(pk=other.pk).exists()
        assert redis_client.exists(f"room:{other.pk}")

    def test_project_deletion(
        self, client, redis_client, project_annotation, django_capture_on_commit_callbacks
    ):
        project = project_annotation["project"]
        second = Batch.objects.create(project=project, batch_number=2)
        batch_ids = [project_annotation["batch"].pk, second.pk]
        for batch_id in batch_ids:
            _chat(batch_id, redis_client)
        client.login(username=project_annotation["expert"].username, password="123")

        with django_capture_on_commit_callbacks(execute=True):
            client.post(reverse("project-delete", args=(project.pk,)))

        assert not Room.objects.filter(pk__in=batch_ids).exists()
        assert not Message.objects.filter(room_id__in=batch_ids).exists()
        assert not any(redis_client.exists(f"room:{batch_id}") for batch_id in batch_ids)

    def test_redis_outage_does_not_block_deletion(
        self, monkeypatch, project_annotation, django_capture_on_commit_callbacks
    ):
        monkeypatch.setattr(room_state, "REDIS_URL", "redis://localhost:1/0")
        batch = project_annotation["batch"]

        with django_capture_on_commit_callbacks(execute=True):
            batch.delete()

        assert not Batch.objects.filter(pk=batch.pk).exists()
