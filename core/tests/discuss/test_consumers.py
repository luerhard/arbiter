import json
import os
import uuid

from asgiref.sync import async_to_sync
from autobahn.exception import Disconnected
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import override_settings
import pytest
import redis

from core.asgi import application
from data.models import Example
from data.models import ExampleAssignment
from data.models.models import Annotation
from data.models.models import Label
from discuss import room_state
from discuss.consumers import ChatConsumer
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
    batch.users.add(user, through_defaults={"role": ProjectRole.ANNOTATOR})
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
def test_discuss_message_appends_to_state(redis_test_state, discussion_with_disagreement):
    user, user2, batch, example, _labels = discussion_with_disagreement
    batch.set_phase(BatchPhase.DISCUSSION)
    message_text = f"hello-{uuid.uuid4().hex}"

    async def run():
        communicator = await _connect(batch, user)
        other = await _connect(batch, user2)
        await _state_where(communicator, lambda s: s["cur_example_id"] == example.id)

        await communicator.send_json_to({"message": message_text})
        await _state_where(
            communicator,
            lambda s: any(
                msg.get("user") == user.username and msg.get("text") == message_text
                for msg in s["messages"]
            ),
        )

        await communicator.disconnect()
        await other.disconnect()

    async_to_sync(run)()
    msg = Message.objects.filter(
        room_id=batch.id,
        user=user.username,
        message=message_text,
    ).first()
    assert msg is not None
    assert msg.example == example  # the chat is kept per discussed example


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
def test_discuss_message_needs_an_open_example(redis_test_state, discussion_with_disagreement):
    # Before the room starts there is no example a message could belong to; the page does
    # not let users chat then, and the server ignores what arrives anyway.
    user, user2, batch, example, _labels = discussion_with_disagreement
    batch.set_phase(BatchPhase.DISCUSSION)

    async def run():
        communicator = await _connect(batch, user)
        await communicator.send_json_to({"message": "anyone here?"})
        other = await _connect(batch, user2)
        await _state_where(communicator, lambda s: s["cur_example_id"] == example.id)
        await communicator.send_json_to({"message": "let's start"})
        state = await _state_where(
            communicator, lambda s: any(m["text"] == "let's start" for m in s["messages"])
        )
        await communicator.disconnect()
        await other.disconnect()
        return state

    state = async_to_sync(run)()
    assert "anyone here?" not in [m["text"] for m in state["messages"]]
    stored = Message.objects.filter(room_id=batch.id, user=user.username)
    assert [(m.message, m.example) for m in stored] == [("let's start", example)]


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
def test_discuss_clicked_done_updates_state(redis_test_state, discussion_with_disagreement):
    user1, user2, batch, example, (label1, _label2) = discussion_with_disagreement
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
        await comm1.receive_json_from()

        await comm1.send_json_to(
            {"clicked-done": True, "labels": [label1.id], "example_id": example.id},
        )
        response = await comm1.receive_json_from()
        state = response["state"]
        assert state["clicked_done"][user1.username] == 1
        assert state["discussion_labels"][user1.username] == [label1.id]
        assert any(
            msg.get("user") == "system"
            and msg.get("text") == f"{user1.username} finalized their decision: ['{label1.name}']"
            for msg in state["messages"]
        )

        await comm1.disconnect()
        await comm2.disconnect()

    async_to_sync(run)()


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
def test_discuss_populates_annotation_labels(redis_test_state, discussion_with_disagreement):
    user1, user2, batch, _example, labels = discussion_with_disagreement
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

        await comm1.send_json_to(
            {"clicked-done": True, "labels": [label1.id], "example_id": example.id},
        )
        await comm1.receive_json_from()
        await comm2.receive_json_from()

        await comm2.send_json_to(
            {"clicked-done": True, "labels": [label2.id], "example_id": example.id},
        )
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

    # Disagreement remains after discussion -> expert decisions are needed.
    batch.refresh_from_db()
    assert batch.current_phase == BatchPhase.EXPERT


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
def test_discuss_agreement_finalizes_batch(redis_test_state, discussion_with_disagreement):
    # Both users converge on the same label during discussion: no expert
    # decisions are needed, so ending the discussion finalizes the batch.
    user1, user2, batch, example, labels = discussion_with_disagreement
    label1, _ = labels
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

        await comm1.send_json_to(
            {"clicked-done": True, "labels": [label1.id], "example_id": example.id},
        )
        await comm1.receive_json_from()
        await comm2.receive_json_from()

        await comm2.send_json_to(
            {"clicked-done": True, "labels": [label1.id], "example_id": example.id},
        )
        await comm1.receive_json_from()
        await comm2.receive_json_from()

        await comm1.disconnect()
        await comm2.disconnect()

    async_to_sync(run)()

    batch.refresh_from_db()
    assert batch.current_phase == BatchPhase.FINAL
    assert not ExampleAssignment.objects.filter(batch=batch, phase=BatchPhase.EXPERT).exists()
    for user in (user1, user2):
        assignment = ExampleAssignment.objects.get(
            batch=batch,
            example=example,
            user=user,
            phase=BatchPhase.DISCUSSION,
        )
        assert list(assignment.annotations.values_list("label_id", flat=True)) == [label1.id]


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
def test_discuss_saves_multiple_and_zero_labels(redis_test_state, discussion_with_disagreement):
    # One user finalizes with ALL labels, the other with NO labels. Both are
    # valid multi-label outcomes (zero labels == "non-offensive") and must be
    # persisted exactly as sent.
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

        await comm1.send_json_to(
            {"clicked-done": True, "labels": [label1.id, label2.id], "example_id": example.id},
        )
        await comm1.receive_json_from()
        await comm2.receive_json_from()

        await comm2.send_json_to(
            {"clicked-done": True, "labels": [], "example_id": example.id},
        )
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
    assert sorted(assignment1.annotations.values_list("label_id", flat=True)) == sorted(
        [label1.id, label2.id],
    )
    assert assignment2.annotations.count() == 0


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
def test_discuss_typing_event_broadcast(redis_test_state, discussion_with_disagreement):
    user1, user2, batch, *_ = discussion_with_disagreement
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

        # Both users receive a state after the second user joins.
        await comm1.receive_json_from()
        await comm2.receive_json_from()

        # user1 starts typing -> user2 sees it, user1 does not.
        await comm1.send_json_to({"typing": True})
        msg = await comm2.receive_json_from()
        assert msg == {"typing": {"user": user1.username, "typing": True}}
        assert await comm1.receive_nothing(timeout=0.2)

        # user1 stops typing -> user2 sees the stop event.
        await comm1.send_json_to({"typing": False})
        msg = await comm2.receive_json_from()
        assert msg == {"typing": {"user": user1.username, "typing": False}}
        assert await comm1.receive_nothing(timeout=0.2)

        await comm1.disconnect()
        await comm2.disconnect()

    async_to_sync(run)()


async def _try_connect(batch, user):
    communicator = WebsocketCommunicator(application, f"/ws/chat/{batch.id}")
    communicator.scope["user"] = user
    connected, _ = await communicator.connect()
    if connected:
        await communicator.disconnect()
    return connected


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
def test_discuss_rejects_anonymous_user(redis_test_state, discussion_setup):
    _, batch = discussion_setup

    assert async_to_sync(_try_connect)(batch, AnonymousUser()) is False


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
def test_discuss_rejects_project_annotator_not_in_batch(redis_test_state, discussion_setup):
    _, batch = discussion_setup
    outsider = User.objects.create_user(
        username=f"not_in_batch_{uuid.uuid4().hex[:8]}",
        password="123",
    )
    ProjectUser.objects.create(
        project=batch.project,
        user=outsider,
        default_role=ProjectRole.ANNOTATOR,
    )

    assert async_to_sync(_try_connect)(batch, outsider) is False


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
def test_discuss_required_users_are_batch_annotators(redis_test_state, discussion_setup):
    user, batch = discussion_setup
    # a project annotator who is not part of this batch must not be waited for
    other = User.objects.create_user(
        username=f"other_batch_{uuid.uuid4().hex[:8]}",
        password="123",
    )
    ProjectUser.objects.create(
        project=batch.project,
        user=other,
        default_role=ProjectRole.ANNOTATOR,
    )
    # a project expert who annotates in this batch must be waited for
    expert = User.objects.create_user(
        username=f"expert_annotator_{uuid.uuid4().hex[:8]}",
        password="123",
    )
    ProjectUser.objects.create(
        project=batch.project,
        user=expert,
        default_role=ProjectRole.EXPERT,
    )
    batch.users.add(expert, through_defaults={"role": ProjectRole.ANNOTATOR})

    async def run():
        communicator = WebsocketCommunicator(application, f"/ws/chat/{batch.id}")
        communicator.scope["user"] = user
        connected, _ = await communicator.connect()
        assert connected is True
        state = (await communicator.receive_json_from())["state"]
        await communicator.disconnect()
        return state

    state = async_to_sync(run)()

    assert set(state["required_users"]) == {user.username, expert.username}


@pytest.fixture
def discussion_three_examples(discussion_with_disagreement):
    """Three examples in batch order: 0 and 2 are disagreements, 1 is agreed on. The
    batch is in the discussion, so 0 and 2 have DISCUSSION assignments."""
    user1, user2, batch, first, labels = discussion_with_disagreement
    label1, label2 = labels
    second = Example.objects.create(batch=batch, content="Agreed example", position=2)
    third = Example.objects.create(batch=batch, content="Second disagreement", position=3)
    Example.objects.filter(pk=first.pk).update(position=1)
    batch.set_phase(BatchPhase.ANNOTATION)  # assignments for the new examples
    for example, (labels1, labels2) in (
        (second, ([label1.id], [label1.id])),
        (third, ([label1.id], [label1.id, label2.id])),
    ):
        _annotation(batch, example, user1).set_user_annotations(labels1)
        _annotation(batch, example, user2).set_user_annotations(labels2)
    batch.set_phase(BatchPhase.DISCUSSION)
    examples = [Example.objects.get(pk=e.pk) for e in (first, second, third)]
    return user1, user2, batch, examples, labels


def _annotation(batch, example, user, phase=BatchPhase.ANNOTATION):
    return ExampleAssignment.objects.get(batch=batch, example=example, user=user, phase=phase)


async def _connect(batch, user):
    communicator = WebsocketCommunicator(application, f"/ws/chat/{batch.id}")
    communicator.scope["user"] = user
    connected, _ = await communicator.connect()
    assert connected is True
    return communicator


async def _state_where(communicator, predicate):
    """Read states until one matches; the number of broadcasts per action varies."""
    while True:
        response = await communicator.receive_json_from(timeout=3)
        state = response.get("state")
        if state and predicate(state):
            return state


def _save(label_ids, example_id):
    return {"clicked-done": True, "labels": label_ids, "example_id": example_id}


async def _both_decide(comm1, comm2, label_ids, cur_example_id):
    """Both annotators save labels for the current example; returns the next state."""
    for communicator in (comm1, comm2):
        await communicator.send_json_to(_save(label_ids, cur_example_id))
    return await _state_where(
        comm1,
        lambda s: s["cur_example_id"] != cur_example_id or s["discussion_ended"],
    )


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
def test_discuss_follows_discussion_assignments_not_live_labels(
    redis_test_state,
    discussion_three_examples,
):
    # Labels that change after the discussion started (e.g. a deleted label, a phase
    # moved back and forth) must not change what the room discusses: it discusses
    # exactly the examples that got DISCUSSION assignments, in order, and never one
    # without (production, 7 Oct 2026: the room crashed on such an example).
    user1, user2, batch, (first, second, third), (label1, label2) = discussion_three_examples
    _annotation(batch, first, user2).set_user_annotations([label1.id])  # now agreed
    _annotation(batch, second, user2).set_user_annotations([label2.id])  # now disagreed

    async def run():
        comm1 = await _connect(batch, user1)
        comm2 = await _connect(batch, user2)

        state = await _state_where(comm1, lambda s: s["cur_example_id"])
        assert (state["cur_example_id"], state["page"], state["total_pages"]) == (first.id, 1, 2)

        state = await _both_decide(comm1, comm2, [label1.id], first.id)
        assert (state["cur_example_id"], state["page"], state["total_pages"]) == (third.id, 2, 2)

        state = await _both_decide(comm1, comm2, [label2.id], third.id)
        assert state["discussion_ended"] == "DISCUSSION_END"

        await comm1.disconnect()
        await comm2.disconnect()

    async_to_sync(run)()

    for example, label in ((first, label1), (third, label2)):
        for user in (user1, user2):
            assignment = _annotation(batch, example, user, BatchPhase.DISCUSSION)
            assert assignment.done is not None
            assert list(assignment.annotations.values_list("label_id", flat=True)) == [label.id]
    assert not ExampleAssignment.objects.filter(example=second, phase=BatchPhase.DISCUSSION)
    batch.refresh_from_db()
    assert batch.current_phase == BatchPhase.FINAL


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
def test_discuss_resumes_after_room_state_lost(redis_test_state, discussion_three_examples):
    # The first example was discussed, then the Redis room state got lost (Redis
    # restarted, resetdb, ...). The room must resume at the next open example
    # instead of starting over and overwriting the decisions already saved.
    user1, user2, batch, (first, _second, third), (label1, _label2) = discussion_three_examples
    for user in (user1, user2):
        _annotation(batch, first, user, BatchPhase.DISCUSSION).set_user_annotations([label1.id])

    async def run():
        comm1 = await _connect(batch, user1)
        comm2 = await _connect(batch, user2)
        state = await _state_where(comm1, lambda s: s["cur_example_id"])
        await comm1.disconnect()
        await comm2.disconnect()
        return state

    state = async_to_sync(run)()

    assert (state["cur_example_id"], state["page"], state["total_pages"]) == (third.id, 2, 2)
    assert not any(m["text"] == "All done. Next Sentence." for m in state["messages"])


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
def test_discuss_resyncs_stale_room_state(redis_test_state, discussion_three_examples):
    # The room state still shows the first example, but it was decided in the
    # meantime (e.g. the room crashed after saving): joining moves on to the next one.
    user1, user2, batch, (first, _second, third), (label1, _label2) = discussion_three_examples

    def decide_first():
        for user in (user1, user2):
            _annotation(batch, first, user, BatchPhase.DISCUSSION).set_user_annotations([label1.id])

    async def run():
        comm1 = await _connect(batch, user1)
        comm2 = await _connect(batch, user2)
        state = await _state_where(comm1, lambda s: s["cur_example_id"])
        assert state["cur_example_id"] == first.id
        await comm1.disconnect()
        await comm2.disconnect()

        await database_sync_to_async(decide_first)()

        comm1 = await _connect(batch, user1)
        comm2 = await _connect(batch, user2)
        state = await _state_where(comm1, lambda s: s["cur_example_id"] == third.id)
        assert state["page"] == 2
        await comm1.disconnect()
        await comm2.disconnect()

    async_to_sync(run)()


def _save_failed(state):
    return "Saving failed. Please save your labels again." in _system_messages(state)


async def _save_one_after_the_other(comm1, comm2, user1, label_ids, example_id):
    """Only the second save completes the example, so exactly one consumer saves."""
    await comm1.send_json_to(_save(label_ids, example_id))
    await _state_where(comm1, lambda s: s["clicked_done"].get(user1.username) == 1)
    await comm2.send_json_to(_save(label_ids, example_id))


def _system_messages(state):
    return [m["text"] for m in state["messages"] if m["user"] == "system"]


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
def test_discuss_failed_save_keeps_room_usable(
    redis_test_state,
    discussion_three_examples,
    monkeypatch,
):
    # Saving the decisions fails (here: once, for the second annotator). Before, the
    # exception ended the consumer and left both Done flags set with locked buttons:
    # the room could never continue. Now nothing is saved, everyone is told, the
    # Done flags reset (the buttons follow them), and saving again works.
    user1, user2, batch, (first, _second, third), (label1, _label2) = discussion_three_examples
    original = ExampleAssignment.set_user_annotations
    failures = []

    def flaky(self, label_ids):
        if self.phase == BatchPhase.DISCUSSION and self.user_id == user2.id and not failures:
            failures.append(self)
            msg = "database hiccup"
            raise RuntimeError(msg)
        return original(self, label_ids)

    monkeypatch.setattr(ExampleAssignment, "set_user_annotations", flaky)

    async def run():
        comm1 = await _connect(batch, user1)
        comm2 = await _connect(batch, user2)
        await _state_where(comm1, lambda s: s["cur_example_id"])
        await _state_where(comm2, lambda s: s["cur_example_id"])

        await _save_one_after_the_other(comm1, comm2, user1, [label1.id], first.id)
        for communicator in (comm1, comm2):
            state = await _state_where(communicator, _save_failed)
        assert set(state["clicked_done"].values()) == {0}
        assert state["saving_example"] is None
        assert state["cur_example_id"] == first.id
        assert "Saving failed. Please save your labels again." in _system_messages(state)
        assert set(state["online_users"]) == {user1.username, user2.username}

        # both connections are still alive: saving again works and moves on
        state = await _both_decide(comm1, comm2, [label1.id], first.id)
        assert state["cur_example_id"] == third.id

        await comm1.disconnect()
        await comm2.disconnect()

    async_to_sync(run)()

    assert failures
    for user in (user1, user2):
        assignment = _annotation(batch, first, user, BatchPhase.DISCUSSION)
        assert list(assignment.annotations.values_list("label_id", flat=True)) == [label1.id]


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
def test_discuss_failed_save_is_all_or_nothing(
    redis_test_state,
    discussion_three_examples,
    monkeypatch,
):
    # the first annotator's decision must not stay saved when the second one fails
    user1, user2, batch, (first, *_), (label1, _label2) = discussion_three_examples
    original = ExampleAssignment.set_user_annotations

    def failing(self, label_ids):
        if self.phase == BatchPhase.DISCUSSION and self.user_id == user2.id:
            msg = "database hiccup"
            raise RuntimeError(msg)
        return original(self, label_ids)

    monkeypatch.setattr(ExampleAssignment, "set_user_annotations", failing)

    async def run():
        comm1 = await _connect(batch, user1)
        comm2 = await _connect(batch, user2)
        await _state_where(comm1, lambda s: s["cur_example_id"])
        await _save_one_after_the_other(comm1, comm2, user1, [label1.id], first.id)
        await _state_where(comm1, _save_failed)
        await comm1.disconnect()
        await comm2.disconnect()

    async_to_sync(run)()

    for user in (user1, user2):
        assignment = _annotation(batch, first, user, BatchPhase.DISCUSSION)
        assert assignment.done is None
        assert not assignment.annotations.exists()


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
@pytest.mark.parametrize(
    "bad",
    [
        lambda _: "not json",
        lambda example_id: json.dumps({"clicked-done": True, "example_id": example_id}),
        lambda example_id: json.dumps(_save("1", example_id)),
        lambda example_id: json.dumps(_save([999_999_999], example_id)),
        lambda _: json.dumps({"clicked-done": True, "labels": []}),
        lambda example_id: json.dumps(_save([], str(example_id))),
        lambda _: json.dumps({"undo-done": True}),
        lambda _: json.dumps({"message": 123}),
    ],
    ids=[
        "not-json",
        "no-labels",
        "labels-not-a-list",
        "unknown-label",
        "no-example",
        "example-not-an-id",
        "undo-no-example",
        "message-not-text",
    ],
)
def test_discuss_bad_message_keeps_room_usable(redis_test_state, discussion_three_examples, bad):
    user1, user2, batch, (first, _second, third), (label1, _label2) = discussion_three_examples

    async def run():
        comm1 = await _connect(batch, user1)
        comm2 = await _connect(batch, user2)
        await _state_where(comm1, lambda s: s["cur_example_id"])

        await comm1.send_to(text_data=bad(first.id))
        state = await _state_where(
            comm1,
            lambda s: any("Saving failed" in t or "went wrong" in t for t in _system_messages(s)),
        )
        assert set(state["clicked_done"].values()) == {0}

        state = await _both_decide(comm1, comm2, [label1.id], first.id)
        assert state["cur_example_id"] == third.id

        await comm1.disconnect()
        await comm2.disconnect()

    async_to_sync(run)()


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
def test_discuss_second_connection_of_a_user_keeps_the_room_working(
    redis_test_state,
    discussion_three_examples,
):
    # A user is connected twice: two tabs, or a reconnect after a network drop while
    # the server has not yet noticed the old socket died. Closing one connection must
    # not take the user out of the room: before, it did, and the remaining one failed
    # on every save (KeyError in clicked_done).
    user1, user2, batch, (first, _second, third), (label1, _label2) = discussion_three_examples

    async def run():
        old = await _connect(batch, user1)
        comm2 = await _connect(batch, user2)
        await _state_where(comm2, lambda s: s["cur_example_id"])
        new = await _connect(batch, user1)
        await _state_where(new, lambda s: s["cur_example_id"] == first.id)

        await old.disconnect()
        state = await room_state.get_state(batch.id)
        assert set(state["online_users"]) == {user1.username, user2.username}
        assert f"{user1.username} has disconnected." not in _system_messages(state)
        assert _system_messages(state).count(f"{user1.username} is now connected.") == 1

        state = await _both_decide(new, comm2, [label1.id], first.id)
        assert state["cur_example_id"] == third.id
        assert "Saving failed. Please save your labels again." not in _system_messages(state)

        await new.disconnect()
        state = await room_state.get_state(batch.id)
        assert state["online_users"] == [user2.username]
        assert f"{user1.username} has disconnected." in _system_messages(state)

        await comm2.disconnect()

    async_to_sync(run)()

    for user in (user1, user2):
        assignment = _annotation(batch, first, user, BatchPhase.DISCUSSION)
        assert list(assignment.annotations.values_list("label_id", flat=True)) == [label1.id]


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
def test_discuss_online_users_follow_open_connections(redis_test_state, discussion_three_examples):
    # A room state from before connections were tracked lists a user as online who
    # is not (a disconnect that never ran). Joining must not start the room for them.
    user1, user2, batch, *_ = discussion_three_examples

    async def run():
        await room_state.set_state(
            batch.id,
            {
                **room_state._defaults(),
                "online_users": [user1.username, user2.username],
                "required_users": sorted([user1.username, user2.username]),
            },
        )
        comm1 = await _connect(batch, user1)
        state = (await comm1.receive_json_from())["state"]
        assert state["online_users"] == [user1.username]
        assert state["page"] == 0
        await comm1.disconnect()

    async_to_sync(run)()


def _undo(example_id):
    return {"undo-done": True, "example_id": example_id}


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
def test_discuss_saved_decision_survives_leaving_the_room(
    redis_test_state,
    discussion_three_examples,
):
    # Before, leaving (a reload, a network drop) silently reset the Done flag while the
    # page kept the button locked: the room waited for a save nobody could click. Now a
    # save stays saved until it is undone or the example is decided.
    user1, user2, batch, (first, _second, third), (label1, label2) = discussion_three_examples

    async def run():
        comm1 = await _connect(batch, user1)
        comm2 = await _connect(batch, user2)
        await _state_where(comm1, lambda s: s["cur_example_id"])

        await comm1.send_json_to(_save([label2.id], first.id))
        await _state_where(comm1, lambda s: s["clicked_done"][user1.username] == 1)
        await comm1.disconnect()

        comm1 = await _connect(batch, user1)
        state = await _state_where(comm1, lambda s: user1.username in s["online_users"])
        assert state["clicked_done"][user1.username] == 1
        assert state["discussion_labels"][user1.username] == [label2.id]
        await comm1.disconnect()

        # both decisions exist, so the example is decided even with user1 away
        await comm2.send_json_to(_save([label1.id], first.id))
        state = await _state_where(comm2, lambda s: s["cur_example_id"] == third.id)
        assert state["clicked_done"] == {user1.username: 0, user2.username: 0}
        assert state["discussion_labels"] == {}
        await comm2.disconnect()

    async_to_sync(run)()

    for user, label in ((user1, label2), (user2, label1)):
        assignment = _annotation(batch, first, user, BatchPhase.DISCUSSION)
        assert list(assignment.annotations.values_list("label_id", flat=True)) == [label.id]


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
def test_discuss_undo_withdraws_a_saved_decision(redis_test_state, discussion_three_examples):
    user1, user2, batch, (first, _second, third), (label1, label2) = discussion_three_examples

    async def run():
        comm1 = await _connect(batch, user1)
        comm2 = await _connect(batch, user2)
        await _state_where(comm1, lambda s: s["cur_example_id"])

        await comm1.send_json_to(_save([label1.id], first.id))
        await _state_where(comm1, lambda s: s["clicked_done"][user1.username] == 1)
        await comm1.send_json_to(_undo(first.id))
        state = await _state_where(comm1, lambda s: s["clicked_done"][user1.username] == 0)
        assert f"{user1.username} withdrew their decision." in _system_messages(state)

        # the other one saving no longer completes the example
        await comm2.send_json_to(_save([label2.id], first.id))
        state = await _state_where(comm1, lambda s: s["clicked_done"][user2.username] == 1)
        assert state["cur_example_id"] == first.id

        # user1 saves again, with another label: that one counts
        await comm1.send_json_to(_save([label2.id], first.id))
        state = await _state_where(comm1, lambda s: s["cur_example_id"] != first.id)
        assert state["cur_example_id"] == third.id

        await comm1.disconnect()
        await comm2.disconnect()

    async_to_sync(run)()

    for user in (user1, user2):
        assignment = _annotation(batch, first, user, BatchPhase.DISCUSSION)
        assert list(assignment.annotations.values_list("label_id", flat=True)) == [label2.id]


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
def test_discuss_repeated_save_does_not_withdraw(redis_test_state, discussion_three_examples):
    # Before, a second save toggled the Done flag back to 0, and the chat still
    # announced a finalized decision.
    user1, user2, batch, (first, *_), (label1, _label2) = discussion_three_examples

    async def run():
        comm1 = await _connect(batch, user1)
        comm2 = await _connect(batch, user2)
        await _state_where(comm1, lambda s: s["cur_example_id"])

        await comm1.send_json_to(_save([label1.id], first.id))
        await comm1.send_json_to(_save([label1.id], first.id))
        await _state_where(comm1, lambda s: s["clicked_done"][user1.username] == 1)
        await comm1.send_json_to({"message": "after the saves"})
        state = await _state_where(comm1, lambda s: s["messages"][-1]["text"] == "after the saves")
        assert state["clicked_done"][user1.username] == 1
        finalized = [t for t in _system_messages(state) if "finalized their decision" in t]
        assert len(finalized) == 1

        await comm1.disconnect()
        await comm2.disconnect()

    async_to_sync(run)()


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
def test_discuss_late_save_and_undo_do_not_touch_the_next_example(
    redis_test_state,
    discussion_three_examples,
):
    # A save or undo that arrives after the room moved on (double click, a message
    # queued during a reconnect) refers to the previous example and is ignored.
    user1, user2, batch, (first, _second, third), (label1, label2) = discussion_three_examples

    async def run():
        comm1 = await _connect(batch, user1)
        comm2 = await _connect(batch, user2)
        await _state_where(comm1, lambda s: s["cur_example_id"])
        await _both_decide(comm1, comm2, [label1.id], first.id)

        await comm1.send_json_to(_save([label2.id], first.id))
        await comm1.send_json_to(_save([label2.id], 0))  # the room before it started
        await comm1.send_json_to({"message": "after the late save"})
        state = await _state_where(
            comm1,
            lambda s: s["messages"][-1]["text"] == "after the late save",
        )
        assert state["cur_example_id"] == third.id
        assert state["clicked_done"][user1.username] == 0
        assert state["discussion_labels"] == {}

        # user2 saved the current example; user1's undo for the old one must not touch it
        await comm2.send_json_to(_save([label1.id], third.id))
        await _state_where(comm1, lambda s: s["clicked_done"][user2.username] == 1)
        await comm2.send_json_to(_undo(first.id))
        await comm2.send_json_to({"message": "after the late undo"})
        state = await _state_where(
            comm1,
            lambda s: s["messages"][-1]["text"] == "after the late undo",
        )
        assert state["clicked_done"][user2.username] == 1
        assert "withdrew their decision" not in " ".join(_system_messages(state))

        await comm1.disconnect()
        await comm2.disconnect()

    async_to_sync(run)()

    for user in (user1, user2):
        assignment = _annotation(batch, first, user, BatchPhase.DISCUSSION)
        assert list(assignment.annotations.values_list("label_id", flat=True)) == [label1.id]


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
def test_discuss_double_save_completes_the_example_once(
    redis_test_state,
    discussion_three_examples,
):
    # The second annotator's save arrives twice at once (double click, two tabs): only
    # one of them may write the decisions and move on, never skip an example.
    user1, user2, batch, (first, _second, third), (label1, _label2) = discussion_three_examples

    async def run():
        comm1 = await _connect(batch, user1)
        tab_a = await _connect(batch, user2)
        tab_b = await _connect(batch, user2)
        await _state_where(comm1, lambda s: s["cur_example_id"])

        await comm1.send_json_to(_save([label1.id], first.id))
        await _state_where(comm1, lambda s: s["clicked_done"][user1.username] == 1)
        await tab_a.send_json_to(_save([label1.id], first.id))
        await tab_b.send_json_to(_save([label1.id], first.id))
        await _state_where(comm1, lambda s: s["cur_example_id"] == third.id)
        await comm1.send_json_to({"message": "after the double save"})
        state = await _state_where(
            comm1,
            lambda s: s["messages"][-1]["text"] == "after the double save",
        )
        assert (state["cur_example_id"], state["page"]) == (third.id, 2)
        assert _system_messages(state).count("All done. Next Sentence.") == 1

        for communicator in (comm1, tab_a, tab_b):
            await communicator.disconnect()

    async_to_sync(run)()

    for user in (user1, user2):
        assignment = _annotation(batch, third, user, BatchPhase.DISCUSSION)
        assert assignment.done is None


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
def test_discuss_room_starts_again_after_moving_back(redis_test_state, discussion_three_examples):
    # The discussion ended, the batch was moved back to annotation, a label changed, and
    # the batch entered the discussion again. Before, the room state still said "ended"
    # and the room never started again.
    user1, user2, batch, (first, second, third), (label1, label2) = discussion_three_examples

    def move_back_and_change_second():
        batch.set_phase(BatchPhase.ANNOTATION)
        _annotation(batch, second, user2).set_user_annotations([label2.id])
        batch.set_phase(BatchPhase.DISCUSSION)

    async def run():
        comm1 = await _connect(batch, user1)
        comm2 = await _connect(batch, user2)
        await _state_where(comm1, lambda s: s["cur_example_id"] == first.id)
        await _both_decide(comm1, comm2, [label1.id], first.id)
        state = await _both_decide(comm1, comm2, [label1.id], third.id)
        assert state["discussion_ended"] == "DISCUSSION_END"
        await comm1.disconnect()
        await comm2.disconnect()

        await database_sync_to_async(move_back_and_change_second)()

        comm1 = await _connect(batch, user1)
        comm2 = await _connect(batch, user2)
        state = await _state_where(comm1, lambda s: s["cur_example_id"])
        assert (state["cur_example_id"], state["page"], state["total_pages"]) == (second.id, 3, 3)
        assert not state["discussion_ended"]
        await comm1.disconnect()
        await comm2.disconnect()

    async_to_sync(run)()


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
def test_discuss_room_is_closed_outside_the_discussion_phase(
    redis_test_state,
    discussion_with_disagreement,
):
    user1, _user2, batch, *_ = discussion_with_disagreement  # in the annotation phase

    assert async_to_sync(_try_connect)(batch, user1) is False


async def _until_closed(communicator):
    """Everything a client receives until the server closes the connection."""
    received = []
    while True:
        output = await communicator.receive_output(timeout=3)
        if output["type"] == "websocket.close":
            return received, output.get("code")
        received.append(json.loads(output["text"]))


def _room_closed(received):
    return next(m["room_closed"] for m in received if "room_closed" in m)


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
@pytest.mark.parametrize(
    ("label_user2", "phase", "message"),
    [
        (
            "other",
            BatchPhase.EXPERT,
            "All disagreements discussed. The batch moves on to expert decisions.",
        ),
        ("same", BatchPhase.FINAL, "All disagreements discussed. The batch is finalized."),
    ],
)
def test_discuss_end_closes_the_room(
    redis_test_state,
    discussion_with_disagreement,
    label_user2,
    phase,
    message,
):
    # Before, the server only marked the room as ended: the open pages kept showing the
    # last sentence with a disabled Save button, which looked like a hang.
    user1, user2, batch, example, (label1, label2) = discussion_with_disagreement
    batch.set_phase(BatchPhase.DISCUSSION)
    labels2 = [label1.id] if label_user2 == "same" else [label2.id]

    async def run():
        comm1 = await _connect(batch, user1)
        comm2 = await _connect(batch, user2)
        await _state_where(comm1, lambda s: s["cur_example_id"] == example.id)
        await _state_where(comm2, lambda s: s["cur_example_id"] == example.id)

        await comm1.send_json_to(_save([label1.id], example.id))
        await _state_where(comm2, lambda s: s["clicked_done"][user1.username] == 1)
        await comm2.send_json_to(_save(labels2, example.id))

        for communicator in (comm1, comm2):
            received, code = await _until_closed(communicator)
            assert code == 1000  # a normal close: the client does not reconnect
            closed = _room_closed(received)
            assert closed["message"] == message
            assert closed["project_url"] == f"/projects/{batch.project_id}"
            last_state = [m["state"] for m in received if "state" in m][-1]
            assert "All Examples discussed." in _system_messages(last_state)

    async_to_sync(run)()

    batch.refresh_from_db()
    assert batch.current_phase == phase


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
def test_discuss_phase_change_closes_the_open_room(redis_test_state, discussion_three_examples):
    user1, user2, batch, (first, *_), _labels = discussion_three_examples

    async def run():
        comm1 = await _connect(batch, user1)
        comm2 = await _connect(batch, user2)
        await _state_where(comm1, lambda s: s["cur_example_id"] == first.id)

        await database_sync_to_async(batch.set_phase)(BatchPhase.ANNOTATION)

        for communicator in (comm1, comm2):
            received, code = await _until_closed(communicator)
            assert code == 1000
            assert _room_closed(received)["message"] == (
                "This batch was moved to the Annotation phase. The discussion is closed."
            )

    async_to_sync(run)()


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
def test_discuss_closed_connection_gets_no_more_messages(
    redis_test_state,
    discussion_three_examples,
):
    # A broadcast that arrives after the room closed a connection, before the client is gone
    # (here: the partner leaving first), must not be sent: daphne raises on the closed
    # socket, which ended the consumer before disconnect() and left the user online.
    user1, user2, batch, (first, *_), _labels = discussion_three_examples

    async def run():
        comm1 = await _connect(batch, user1)
        comm2 = await _connect(batch, user2)
        await _state_where(comm1, lambda s: s["cur_example_id"] == first.id)
        await database_sync_to_async(batch.set_phase)(BatchPhase.ANNOTATION)
        for communicator in (comm1, comm2):
            await _until_closed(communicator)

        await comm2.disconnect()  # broadcasts "... has disconnected"

        assert await comm1.receive_nothing(timeout=0.5)
        await comm1.disconnect()
        return await room_state.get_state(batch.id)

    state = async_to_sync(run)()
    assert (state["online_users"], state["connections"]) == ([], {})


def test_discuss_send_to_a_client_that_is_gone_keeps_the_consumer():
    # e.g. a closed tab: the consumer has to live on until disconnect() cleans up
    consumer = ChatConsumer()
    consumer.batch_id, consumer.username = 1, "someone"

    async def closed_socket(message):
        msg = "Attempt to send on a closed protocol"
        raise Disconnected(msg)

    consumer.base_send = closed_socket

    async_to_sync(consumer.send)(text_data="{}")  # does not raise


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
def test_discuss_save_after_the_phase_changed_is_not_stored(
    redis_test_state,
    discussion_three_examples,
):
    # a save that arrives after the phase changed but before the room closed
    user1, user2, batch, (first, *_), (label1, _label2) = discussion_three_examples

    async def run():
        comm1 = await _connect(batch, user1)
        comm2 = await _connect(batch, user2)
        await _state_where(comm1, lambda s: s["cur_example_id"] == first.id)

        # the phase alone, without set_phase() closing the room
        await database_sync_to_async(
            Batch.objects.filter(pk=batch.pk).update,
        )(current_phase=BatchPhase.ANNOTATION)
        for communicator in (comm1, comm2):
            await communicator.send_json_to(_save([label1.id], first.id))
        state = await _state_where(
            comm1,
            lambda s: (
                _system_messages(s).count(
                    "This batch is no longer in the discussion phase. Nothing was saved.",
                )
                == 2
            ),
        )
        assert state["clicked_done"][user1.username] == 0

        await comm1.disconnect()
        await comm2.disconnect()

    async_to_sync(run)()

    for user in (user1, user2):
        assignment = _annotation(batch, first, user, BatchPhase.DISCUSSION)
        assert assignment.done is None
        assert not assignment.annotations.exists()


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
def test_discuss_nothing_to_discuss_closes_the_room(redis_test_state, discussion_setup):
    # Before, the page kept saying "Waiting for others to arrive..." forever.
    user, batch = discussion_setup  # in the discussion phase, without examples

    async def run():
        communicator = await _connect(batch, user)
        received, code = await _until_closed(communicator)
        assert code == 1000
        assert _room_closed(received)["message"] == (
            "There was nothing to discuss. The batch is finalized."
        )

    async_to_sync(run)()
