"""End-to-end tests for label persistence across all three phases.

Saving labels correctly in Annotation, Discussion and Expert phase is the
core feature of the tool. These tests drive ONE example through the whole
pipeline using the real interfaces (HTTP views for annotation/expert, the
websocket consumer for discussion) and verify after every phase that the
database contains exactly the labels each user submitted.

Covered label combinations per phase: no labels (a valid verdict under
multi-label annotation, e.g. "non-offensive"), a single label, and multiple
labels.

Phase transitions are not set manually: the test relies on the auto-increment
feature (annotators finalizing moves ANNOTATION -> DISCUSSION, the discussion
ending moves DISCUSSION -> EXPERT, the last expert decision -> FINAL).
"""

import os

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.test import Client
from django.test import override_settings
from django.urls import reverse
import pytest
import redis

from core.asgi import application
from data.models import ExampleAssignment
from discuss import room_state
from projects.models import BatchPhase

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


def _assignment(batch, user, example, phase):
    return ExampleAssignment.objects.get(batch=batch, user=user, example=example, phase=phase)


def _stored_label_ids(assignment):
    return sorted(assignment.annotations.values_list("label_id", flat=True))


def _annotate_via_http(user, batch, example, label_ids):
    """Save labels for one annotator through the annotation view."""
    client = Client()
    assert client.login(username=user.username, password="123") is True
    assignment = _assignment(batch, user, example, BatchPhase.ANNOTATION)
    url = reverse("annotate-assignment", args=(batch.id, assignment.id))
    response = client.post(url, data={"labels": label_ids}, HTTP_HX_REQUEST="true")
    # Single-example batch: saving the last assignment redirects to done.
    assert response.status_code in (200, 302)
    return assignment


def _discuss_via_websocket(user1, user2, batch, labels_user1, labels_user2):
    """Both annotators finalize their decision through the chat consumer."""

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

        await comm1.send_json_to({"clicked-done": True, "labels": labels_user1})
        await comm1.receive_json_from()
        await comm2.receive_json_from()

        await comm2.send_json_to({"clicked-done": True, "labels": labels_user2})
        await comm1.receive_json_from()
        await comm2.receive_json_from()

        await comm1.disconnect()
        await comm2.disconnect()

    async_to_sync(run)()


def _expert_decision_via_http(expert, batch, example, label_ids):
    """Save the final decision through the expert view.

    A label-only decision carries no codebook fields at all: codebook edits
    are separate server-side drafts.
    """
    client = Client()
    assert client.login(username=expert.username, password="123") is True
    assignment = _assignment(batch, expert, example, BatchPhase.EXPERT)
    url = reverse("expert-assignment", args=(batch.id, assignment.id))
    response = client.post(url, data={"labels": label_ids})
    assert response.status_code == 302
    return assignment


# Each scenario: (annotation a1, annotation a2, discussion a1, discussion a2,
# expert). Annotation and discussion labels must disagree between the two
# annotators, otherwise the example never reaches the next phase.
SCENARIOS = [
    pytest.param(
        {"a1": "single", "a2": "multiple"},
        {"a1": "none", "a2": "multiple"},
        "multiple",
        id="single-vs-multiple--expert-multiple",
    ),
    pytest.param(
        {"a1": "none", "a2": "single"},
        {"a1": "none", "a2": "single"},
        "none",
        id="none-vs-single--expert-none",
    ),
    pytest.param(
        {"a1": "multiple", "a2": "none"},
        {"a1": "single", "a2": "multiple"},
        "single",
        id="multiple-vs-none--expert-single",
    ),
]


@pytest.mark.django_db(transaction=True)
@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
@pytest.mark.parametrize(("annotation", "discussion", "expert_choice"), SCENARIOS)
def test_labels_survive_full_pipeline(
    redis_test_state,
    project_annotation,
    annotation,
    discussion,
    expert_choice,
):
    data = project_annotation
    a1, a2 = data["annotators"]
    expert = data["expert"]
    batch = data["batch"]
    example = data["example"]
    label1, label2 = data["labels"]

    combos = {
        "none": [],
        "single": [label1.id],
        "multiple": [label1.id, label2.id],
    }

    # --- Phase 1: Annotation (HTTP) -------------------------------------
    for user, choice in ((a1, annotation["a1"]), (a2, annotation["a2"])):
        assignment = _annotate_via_http(user, batch, example, combos[choice])
        assignment.refresh_from_db()
        assert assignment.done is not None
        assert _stored_label_ids(assignment) == sorted(combos[choice])

    # --- Phase transition: both annotators finalize (HTTP) ---------------
    # Auto-advance: disagreements exist, so the batch moves to DISCUSSION.
    for user in (a1, a2):
        client = Client()
        assert client.login(username=user.username, password="123") is True
        response = client.post(reverse("annotate-done", args=(batch.id,)))
        assert response.status_code == 302
    batch.refresh_from_db()
    assert batch.current_phase == BatchPhase.DISCUSSION
    assert example in batch.disagreements(BatchPhase.ANNOTATION)

    _discuss_via_websocket(a1, a2, batch, combos[discussion["a1"]], combos[discussion["a2"]])

    for user, choice in ((a1, discussion["a1"]), (a2, discussion["a2"])):
        assignment = _assignment(batch, user, example, BatchPhase.DISCUSSION)
        assert assignment.done is not None
        assert _stored_label_ids(assignment) == sorted(combos[choice])

    # Annotation-phase labels must remain untouched by the discussion save.
    for user, choice in ((a1, annotation["a1"]), (a2, annotation["a2"])):
        assignment = _assignment(batch, user, example, BatchPhase.ANNOTATION)
        assert _stored_label_ids(assignment) == sorted(combos[choice])

    # --- Phase 3: Expert decision (HTTP) ----------------------------------
    # Auto-advance: the discussion ended with disagreement in every scenario,
    # so the consumer moved the batch to EXPERT without manual intervention.
    batch.refresh_from_db()
    assert batch.current_phase == BatchPhase.EXPERT
    assert example in batch.disagreements(BatchPhase.DISCUSSION)

    assignment = _expert_decision_via_http(expert, batch, example, combos[expert_choice])
    assignment.refresh_from_db()
    assert assignment.done is not None
    assert _stored_label_ids(assignment) == sorted(combos[expert_choice])

    example.refresh_from_db()
    assert example.has_expert_decision

    # Saving the last expert decision finalizes the batch.
    batch.refresh_from_db()
    assert batch.current_phase == BatchPhase.FINAL

    # Earlier phases are still intact after the expert save.
    for user, choice in ((a1, discussion["a1"]), (a2, discussion["a2"])):
        assert _stored_label_ids(
            _assignment(batch, user, example, BatchPhase.DISCUSSION),
        ) == sorted(combos[choice])
    for user, choice in ((a1, annotation["a1"]), (a2, annotation["a2"])):
        assert _stored_label_ids(
            _assignment(batch, user, example, BatchPhase.ANNOTATION),
        ) == sorted(combos[choice])
