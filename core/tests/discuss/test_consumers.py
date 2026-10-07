import json
import os
import uuid

from asgiref.sync import async_to_sync
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
    label = Label.objects.create(project=batch.project, name="L1")

    async def run():
        communicator = WebsocketCommunicator(application, f"/ws/chat/{batch.id}")
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        assert connected is True

        await communicator.receive_json_from()

        await communicator.send_json_to({"clicked-done": True, "labels": [label.id]})
        response = await communicator.receive_json_from()
        state = response["state"]
        assert state["clicked_done"][user.username] == 1
        assert state["discussion_labels"][user.username] == [label.id]
        assert any(
            msg.get("user") == "system"
            and msg.get("text") == f"{user.username} finalized their decision: ['{label.name}']"
            for msg in state["messages"]
        )

        await communicator.disconnect()

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

        await comm1.send_json_to({"clicked-done": True, "labels": [label1.id]})
        await comm1.receive_json_from()
        await comm2.receive_json_from()

        await comm2.send_json_to({"clicked-done": True, "labels": [label1.id]})
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

        await comm1.send_json_to({"clicked-done": True, "labels": [label1.id, label2.id]})
        await comm1.receive_json_from()
        await comm2.receive_json_from()

        await comm2.send_json_to({"clicked-done": True, "labels": []})
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


async def _both_decide(comm1, comm2, label_ids, cur_example_id):
    """Both annotators save labels for the current example; returns the next state."""
    for communicator in (comm1, comm2):
        await communicator.send_json_to({"clicked-done": True, "labels": label_ids})
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


async def _message_where(communicator, predicate):
    while True:
        message = await communicator.receive_json_from(timeout=3)
        if predicate(message):
            return message


async def _save_one_after_the_other(comm1, comm2, user1, label_ids):
    """Only the second save completes the example, so exactly one consumer saves."""
    await comm1.send_json_to({"clicked-done": True, "labels": label_ids})
    await _state_where(comm1, lambda s: s["clicked_done"].get(user1.username) == 1)
    await comm2.send_json_to({"clicked-done": True, "labels": label_ids})


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
    # buttons unlock, and saving again works.
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

        await _save_one_after_the_other(comm1, comm2, user1, [label1.id])
        for communicator in (comm1, comm2):
            await _message_where(communicator, lambda m: m.get("save_failed"))
        state = await room_state.get_state(batch.id)
        assert set(state["clicked_done"].values()) == {0}
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
        await _save_one_after_the_other(comm1, comm2, user1, [label1.id])
        await _message_where(comm1, lambda m: m.get("save_failed"))
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
        "not json",
        json.dumps({"clicked-done": True}),
        json.dumps({"clicked-done": True, "labels": "1"}),
        json.dumps({"clicked-done": True, "labels": [999_999_999]}),
        json.dumps({"message": 123}),
    ],
)
def test_discuss_bad_message_keeps_room_usable(redis_test_state, discussion_three_examples, bad):
    user1, user2, batch, (first, _second, third), (label1, _label2) = discussion_three_examples

    async def run():
        comm1 = await _connect(batch, user1)
        comm2 = await _connect(batch, user2)
        await _state_where(comm1, lambda s: s["cur_example_id"])

        await comm1.send_to(text_data=bad)
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
