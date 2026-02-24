import os
import uuid

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import override_settings
import pytest
import redis

from core.asgi import application
from data.models import Example
from data.models import ExampleAssignment
from data.models.models import Annotation
from data.models.models import Label
from discuss import room_state
from discuss.models import Message
from projects.models import Batch
from projects.models import BatchPhase
from projects.models import Project
from projects.models import ProjectRole
from projects.models import ProjectUser

User = get_user_model()

TEST_CHANNEL_LAYERS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
}


@pytest.fixture
def redis_test_state(monkeypatch):
    redis_host = os.environ.get("REDIS_HOST", "localhost")
    url = f"redis://{redis_host}:6379/15"
    monkeypatch.setattr(room_state, "REDIS_URL", url)
    room_state._redis = None
    client = redis.Redis.from_url(url, decode_responses=True)
    client.flushdb()
    yield
    room_state._redis = None
    client.flushdb()
    client.close()


@pytest.fixture
def discussion_setup(db):
    user = User.objects.filter(username="annotator1").first()
    if user is None:
        user = User.objects.create_user(username="annotator1", password="123")

    project = Project.objects.filter(name="Test Project").first()
    if project is None:
        project = Project.objects.create(name="Test Project", description="Test Desc", owner=user)

    ProjectUser.objects.get_or_create(
        project=project,
        user=user,
        defaults={"default_role": ProjectRole.ANNOTATOR},
    )
    batch = Batch.objects.create(project=project, current_phase=BatchPhase.DISCUSSION)
    return user, batch


@pytest.fixture
def discussion_with_disagreement(db):
    user1, _ = User.objects.get_or_create(username="discuss_annotator_1")
    user2, _ = User.objects.get_or_create(username="discuss_annotator_2")

    project = Project.objects.create(
        name="Discuss Project",
        description="Discuss Desc",
        owner=user1,
    )
    ProjectUser.objects.create(
        project=project,
        user=user1,
        default_role=ProjectRole.ANNOTATOR,
    )
    ProjectUser.objects.create(
        project=project,
        user=user2,
        default_role=ProjectRole.ANNOTATOR,
    )

    label1 = Label.objects.create(project=project, name="Label A")
    label2 = Label.objects.create(project=project, name="Label B")

    batch = Batch.objects.create(project=project)
    batch.users.add(user1, user2, through_defaults={"role": ProjectRole.ANNOTATOR})
    ex = Example.objects.create(batch=batch, content="Example with disagreement")

    batch.set_phase(BatchPhase.ANNOTATION)

    a1 = ExampleAssignment.objects.filter(
        batch=batch,
        example=ex,
        user=user1,
        phase=BatchPhase.ANNOTATION,
    ).get()
    a2 = ExampleAssignment.objects.filter(
        batch=batch,
        example=ex,
        user=user2,
        phase=BatchPhase.ANNOTATION,
    ).get()

    Annotation.objects.create(assignment=a1, label=label1)
    Annotation.objects.create(assignment=a2, label=label2)

    return user1, user2, batch, ex, [label1, label2]


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
def test_discuss_connect_sets_users(redis_test_state, discussion_setup):
    user, batch = discussion_setup

    async def run():
        communicator = WebsocketCommunicator(application, f"/ws/chat/{batch.id}")
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        assert connected is True

        response = await communicator.receive_json_from()
        state = response["state"]
        assert user.username in state["online_users"]
        assert user.username in state["required_users"]

        await communicator.disconnect()

    async_to_sync(run)()


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
def test_discuss_message_appends_to_state(redis_test_state, discussion_setup):
    user, batch = discussion_setup
    message_text = f"hello-{uuid.uuid4().hex}"
    Message.objects.filter(room_id=batch.id, user=user.username).delete()

    async def run():
        communicator = WebsocketCommunicator(application, f"/ws/chat/{batch.id}")
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        assert connected is True

        await communicator.receive_json_from()

        await communicator.send_json_to({"message": message_text})
        response = await communicator.receive_json_from()
        state = response["state"]
        assert any(
            msg.get("user") == user.username and msg.get("text") == message_text
            for msg in state["messages"]
        )

        await communicator.disconnect()

    async_to_sync(run)()
    msg = Message.objects.filter(
        room_id=batch.id,
        user=user.username,
        message=message_text,
    ).first()
    assert msg is not None
    assert msg.example is None


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
def test_discuss_clicked_done_updates_state(redis_test_state, discussion_setup):
    user, batch = discussion_setup

    async def run():
        communicator = WebsocketCommunicator(application, f"/ws/chat/{batch.id}")
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        assert connected is True

        await communicator.receive_json_from()

        await communicator.send_json_to({"clicked-done": True, "labels": [1]})
        response = await communicator.receive_json_from()
        state = response["state"]
        assert state["clicked_done"][user.username] == 1
        assert state["discussion_labels"][user.username] == [1]

        await communicator.disconnect()

    async_to_sync(run)()


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
def test_discuss_populates_annotation_labels(redis_test_state, discussion_with_disagreement):
    user1, user2, batch, _example, labels = discussion_with_disagreement

    async def run():
        comm1 = WebsocketCommunicator(application, f"/ws/chat/{batch.id}")
        comm1.scope["user"] = user1
        connected, _ = await comm1.connect()
        assert connected is True
        await comm1.receive_json_from()

        comm2 = WebsocketCommunicator(application, f"/ws/chat/{batch.id}")
        comm2.scope["user"] = user2
        connected, _ = await comm2.connect()
        assert connected is True

        state = None
        for _ in range(3):
            response = await comm2.receive_json_from()
            state = response.get("state")
            if state and state.get("annotation_labels"):
                break

        assert state is not None
        assert state["annotation_labels"]

        for username in [user1.username, user2.username]:
            user_labels = state["annotation_labels"][username]
            assert len(user_labels) == len(labels)
            first = user_labels[0]
            if isinstance(first, (list, tuple)):
                first = first[0]
            assert isinstance(first, dict)
            assert "id" in first
            assert "label" in first
            assert "color" in first
            assert "is_set" in first

        await comm1.disconnect()
        await comm2.disconnect()

    async_to_sync(run)()


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
def test_discuss_two_users_save_discussion_decisions(
    redis_test_state,
    discussion_with_disagreement,
):
    user1, user2, batch, example, labels = discussion_with_disagreement
    label1, label2 = labels
    batch.set_phase(BatchPhase.DISCUSSION)

    async def run():
        comm1 = WebsocketCommunicator(application, f"/ws/chat/{batch.id}")
        comm1.scope["user"] = user1
        connected, _ = await comm1.connect()
        assert connected is True
        await comm1.receive_json_from()

        comm2 = WebsocketCommunicator(application, f"/ws/chat/{batch.id}")
        comm2.scope["user"] = user2
        connected, _ = await comm2.connect()
        assert connected is True

        # Both users receive a state after second user joins.
        await comm1.receive_json_from()
        await comm2.receive_json_from()

        await comm1.send_json_to({"clicked-done": True, "labels": [label1.id]})
        await comm1.receive_json_from()
        await comm2.receive_json_from()

        await comm2.send_json_to({"clicked-done": True, "labels": [label2.id]})
        await comm1.receive_json_from()
        await comm2.receive_json_from()

        await comm1.disconnect()
        await comm2.disconnect()

    async_to_sync(run)()

    assignment1 = ExampleAssignment.objects.get(
        batch=batch,
        example=example,
        user=user1,
        phase=BatchPhase.DISCUSSION,
    )
    assignment2 = ExampleAssignment.objects.get(
        batch=batch,
        example=example,
        user=user2,
        phase=BatchPhase.DISCUSSION,
    )

    assert assignment1.done is not None
    assert assignment2.done is not None
    assert list(assignment1.annotations.values_list("label_id", flat=True)) == [label1.id]
    assert list(assignment2.annotations.values_list("label_id", flat=True)) == [label2.id]
