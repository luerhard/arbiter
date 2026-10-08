"""The samples table of a batch: experts see every example with its metadata
and can rearrange the order in which annotators get them."""

import json

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
import pytest

from data.models import Example
from data.models import ExampleAssignment
from discuss.models import Message
from discuss.models import Room
from projects.models import Batch
from projects.models import BatchPhase
from projects.models import ProjectRole
from projects.models import ProjectUser

User = get_user_model()


@pytest.fixture
def batch_with_three(project_annotation):
    """A batch in annotation with three examples A, B, C (in that order)."""
    data = project_annotation
    batch = Batch.objects.create(project=data["project"])
    batch.users.add(*data["annotators"], through_defaults={"role": ProjectRole.ANNOTATOR})
    batch.users.add(data["expert"], through_defaults={"role": ProjectRole.EXPERT})
    examples = [
        Example.objects.create(batch=batch, content=text, position=i, metadata={"id": i})
        for i, text in enumerate(["A", "B", "C"], start=1)
    ]
    batch.set_phase(BatchPhase.ANNOTATION)
    return {**data, "batch": batch, "examples": examples}


def _login(client, user):
    assert client.login(username=user.username, password="123")


def _reorder(client, batch, examples):
    return client.post(
        reverse("project-batch-order", args=(batch.id,)),
        {"example": [e.id for e in examples]},
        HTTP_HX_REQUEST="true",
    )


@pytest.mark.django_db
class TestSamplesTable:
    def test_expert_sees_texts_and_metadata_in_order(self, client, batch_with_three):
        _login(client, batch_with_three["expert"])

        response = client.get(reverse("project-batch-detail", args=(batch_with_three["batch"].id,)))

        assert response.status_code == 200
        assert [e.content for e in response.context["examples"]] == ["A", "B", "C"]
        assert response.context["metadata_columns"] == ["id"]

    def test_upload_numbers_examples_in_file_order(self, client, project_annotation):
        project = project_annotation["project"]
        _login(client, project_annotation["expert"])
        client.post(
            reverse("project-batch-create", args=(project.id,)),
            {
                "file": SimpleUploadedFile("x.csv", b"text\nfirst\nsecond\n"),
                "annotators": [a.id for a in project_annotation["annotators"]],
                "experts": [project_annotation["expert"].id],
            },
        )

        batch = project.batches.order_by("-batch_number").first()
        assert list(batch.examples.values_list("content", "position")) == [
            ("first", 1),
            ("second", 2),
        ]


@pytest.mark.django_db
class TestReorder:
    def test_new_order_reaches_the_annotators(self, client, batch_with_three):
        batch = batch_with_three["batch"]
        a, b, c = batch_with_three["examples"]
        _login(client, batch_with_three["expert"])

        response = _reorder(client, batch, [c, a, b])

        assert response.status_code == 200
        assert [e.content for e in batch.examples.all()] == ["C", "A", "B"]
        for annotator in batch_with_three["annotators"]:
            queue = ExampleAssignment.objects.filter(
                batch=batch,
                user=annotator,
                phase=BatchPhase.ANNOTATION,
            ).order_by("order")
            assert [x.example.content for x in queue] == ["C", "A", "B"]

    def test_annotation_starts_with_the_new_first_sample(self, client, batch_with_three):
        batch = batch_with_three["batch"]
        a, b, c = batch_with_three["examples"]
        _login(client, batch_with_three["expert"])
        _reorder(client, batch, [b, c, a])

        _login(client, batch_with_three["annotators"][0])
        entry = client.get(reverse("annotate-batch", args=(batch.id,)))

        first = client.get(entry.url)
        assert first.context["example"] == b

    def test_later_phases_follow_the_order(self, client, batch_with_three):
        batch = batch_with_three["batch"]
        a, b, c = batch_with_three["examples"]
        _login(client, batch_with_three["expert"])
        _reorder(client, batch, [c, b, a])

        # every phase numbers its assignments the same way (discussion and expert decision
        # only take the disagreements), so recreating them shows what later phases get
        ExampleAssignment.objects.filter(batch=batch).delete()
        batch._create_example_assignments(phase=BatchPhase.ANNOTATION)

        annotator = batch_with_three["annotators"][0]
        queue = ExampleAssignment.objects.filter(batch=batch, user=annotator).order_by("order")
        assert [(x.example.content, x.order) for x in queue] == [("C", 1), ("B", 2), ("A", 3)]

    def test_rejected_once_the_discussion_started(self, client, batch_with_three):
        batch = batch_with_three["batch"]
        a, b, c = batch_with_three["examples"]
        batch.set_phase(BatchPhase.DISCUSSION)
        _login(client, batch_with_three["expert"])

        response = _reorder(client, batch, [c, b, a])

        assert response.status_code == 409
        assert [e.content for e in batch.examples.all()] == ["A", "B", "C"]

    def test_rejected_when_examples_do_not_match_the_batch(self, client, batch_with_three):
        batch = batch_with_three["batch"]
        a, b, _ = batch_with_three["examples"]
        _login(client, batch_with_three["expert"])

        response = _reorder(client, batch, [b, a])

        assert response.status_code == 400
        assert [e.content for e in batch.examples.all()] == ["A", "B", "C"]

    def test_annotator_cannot_reorder(self, client, batch_with_three):
        batch = batch_with_three["batch"]
        a, b, c = batch_with_three["examples"]
        _login(client, batch_with_three["annotators"][0])

        response = _reorder(client, batch, [c, b, a])

        assert response.status_code == 403
        assert [e.content for e in batch.examples.all()] == ["A", "B", "C"]


@pytest.mark.django_db
class TestAnnotationsInTable:
    def _table(self, client, data):
        _login(client, data["expert"])
        response = client.get(reverse("project-batch-detail", args=(data["batch"].id,)))
        return response.context

    def _label(self, batch, annotator, example, labels):
        assignment = ExampleAssignment.objects.get(
            batch=batch,
            user=annotator,
            example=example,
            phase=BatchPhase.ANNOTATION,
        )
        assignment.set_user_annotations(label_ids=[label.id for label in labels])

    def test_status_and_label_instead_of_a_column_per_person(self, client, batch_with_three):
        # as wide for two annotators as for six: who chose what is on the sample's page
        data = batch_with_three
        _login(client, data["expert"])

        response = client.get(reverse("project-batch-detail", args=(data["batch"].id,)))

        content = response.content.decode()
        thead = content[content.index("<thead>") : content.index("</thead>")]
        assert "Status" in thead
        assert "Label" in thead
        for annotator in data["annotators"]:
            assert annotator.username not in thead
        assert "people" not in response.context

    def test_rows_link_to_the_sample(self, client, batch_with_three):
        data = batch_with_three
        _login(client, data["expert"])

        response = client.get(reverse("project-batch-detail", args=(data["batch"].id,)))

        for example in data["examples"]:
            url = reverse("project-sample-detail", args=(data["batch"].id, example.id))
            assert f"window.location = '{url}'" in response.content.decode()
        assert "{#" not in response.content.decode()  # a template comment shown as text

    def test_rows_where_annotators_disagree_are_marked(self, client, batch_with_three):
        data = batch_with_three
        batch, (a, b, c) = data["batch"], data["examples"]
        first, second = data["annotators"]
        label_1, label_2 = data["labels"]
        self._label(batch, first, a, [label_1])
        self._label(batch, second, a, [label_2])
        self._label(batch, first, b, [label_1])
        self._label(batch, second, b, [label_1])

        context = self._table(client, data)

        assert [row["disagreement"] for row in context["rows"]] == [True, False, False]


@pytest.mark.django_db
class TestSampleDetail:
    def _url(self, batch, example):
        return reverse("project-sample-detail", args=(batch.id, example.id))

    def test_shows_text_metadata_labels_chat_and_decision(self, client, project_annotation):
        data = project_annotation
        batch, example = data["batch"], data["example"]
        first, second = data["annotators"]
        label_1, label_2 = data["labels"]
        example.metadata = {"source": "twitter"}
        example.save()

        def label(user, phase, labels):
            ExampleAssignment.objects.get(
                batch=batch,
                user=user,
                example=example,
                phase=phase,
            ).set_user_annotations(label_ids=[x.id for x in labels])

        label(first, BatchPhase.ANNOTATION, [label_1])
        label(second, BatchPhase.ANNOTATION, [label_2])
        batch.set_phase(BatchPhase.DISCUSSION)
        label(first, BatchPhase.DISCUSSION, [label_1])
        label(second, BatchPhase.DISCUSSION, [label_2])
        Message.objects.create(
            room=Room.objects.create(),
            user=first.username,
            example=example,
            message="hm",
        )
        batch.set_phase(BatchPhase.EXPERT)
        label(data["expert"], BatchPhase.EXPERT, [label_2])
        _login(client, data["expert"])

        response = client.get(self._url(batch, example))

        assert response.status_code == 200
        assert response.context["example"] == example
        names = lambda by_user: {u: [a.label.name for a in anns] for u, anns in by_user.items()}  # noqa: E731
        assert names(response.context["before"]) == {
            first.username: [label_1.name],
            second.username: [label_2.name],
        }
        assert names(response.context["decision"]) == {data["expert"].username: [label_2.name]}
        assert [m.message for m in response.context["chat"]] == ["hm"]
        assert b"twitter" in response.content

    def test_unlabeled_sample_shows_not_labeled_yet(self, client, project_annotation):
        data = project_annotation
        _login(client, data["expert"])

        response = client.get(self._url(data["batch"], data["example"]))

        assert set(response.context["before"].values()) == {None}
        assert response.context["decision"] == {}

    def test_previous_and_next_follow_the_batch_order(self, client, batch_with_three):
        batch, (a, b, c) = batch_with_three["batch"], batch_with_three["examples"]
        _login(client, batch_with_three["expert"])

        response = client.get(self._url(batch, b))

        assert (response.context["previous"], response.context["next"]) == (a, c)
        assert response.context["number"] == 2

    def test_example_of_another_batch_is_not_found(self, client, batch_with_three):
        # project_annotation's example belongs to the fixture's first batch
        _login(client, batch_with_three["expert"])
        other = Example.objects.exclude(batch=batch_with_three["batch"]).filter(
            batch__project=batch_with_three["project"],
        )[0]

        response = client.get(self._url(batch_with_three["batch"], other))

        assert response.status_code == 404


@pytest.mark.django_db
class TestDisagreementMarker:
    """The dot in the samples table: only once every annotator has labeled the sample."""

    def _label(self, batch, annotator, example, labels):
        ExampleAssignment.objects.get(
            batch=batch,
            user=annotator,
            example=example,
            phase=BatchPhase.ANNOTATION,
        ).set_user_annotations(label_ids=[label.id for label in labels])

    def _marked(self, client, data):
        _login(client, data["expert"])
        response = client.get(reverse("project-batch-detail", args=(data["batch"].id,)))
        return [row["disagreement"] for row in response.context["rows"]]

    def test_not_marked_while_an_annotator_is_missing(self, client, batch_with_three):
        # Regression: an annotator who had not labeled yet counted as "no label",
        # so every sample the other one labeled was marked.
        data = batch_with_three
        batch, (a, b, _) = data["batch"], data["examples"]
        first, _second = data["annotators"]
        self._label(batch, first, a, [data["labels"][0]])
        self._label(batch, first, b, [])

        assert self._marked(client, data) == [False, False, False]

    def test_label_versus_no_label_is_marked(self, client, batch_with_three):
        data = batch_with_three
        batch, (a, b, _) = data["batch"], data["examples"]
        first, second = data["annotators"]
        self._label(batch, first, a, [data["labels"][0]])
        self._label(batch, second, a, [])
        self._label(batch, first, b, [])
        self._label(batch, second, b, [])

        assert self._marked(client, data) == [True, False, False]


def _label(batch, user, example, labels, phase=BatchPhase.ANNOTATION):
    ExampleAssignment.objects.get(
        batch=batch,
        user=user,
        example=example,
        phase=phase,
    ).set_user_annotations(label_ids=[label.id for label in labels])


@pytest.mark.django_db
class TestSampleStatus:
    """How far each sample got and its label so far: the expert decision, else what the
    discussion agreed on, else what the annotators agreed on."""

    def _rows(self, client, data):
        _login(client, data["expert"])
        response = client.get(reverse("project-batch-detail", args=(data["batch"].id,)))
        return [
            (row["status"], None if row["labels"] is None else [x.name for x in row["labels"]])
            for row in response.context["rows"]
        ]

    def test_during_annotation(self, client, batch_with_three):
        data = batch_with_three
        batch, (a, b, c) = data["batch"], data["examples"]
        first, second = data["annotators"]
        label_1, _label_2 = data["labels"]
        assert self._rows(client, data) == [("Labeled 0 of 2", None)] * 3

        _label(batch, first, a, [label_1])
        _label(batch, second, a, [label_1])
        _label(batch, first, b, [label_1])
        _label(batch, second, b, [])
        _label(batch, first, c, [])

        assert self._rows(client, data) == [
            ("Agreed", [label_1.name]),
            ("To be discussed", None),
            ("Labeled 1 of 2", None),
        ]

    def test_agreed_on_no_label(self, client, batch_with_three):
        data = batch_with_three
        batch, (a, _b, _c) = data["batch"], data["examples"]
        for annotator in data["annotators"]:
            _label(batch, annotator, a, [])

        assert self._rows(client, data)[0] == ("Agreed", [])

    def test_through_discussion_and_expert(self, client, batch_with_three):
        data = batch_with_three
        batch, (a, b, c) = data["batch"], data["examples"]
        first, second = data["annotators"]
        label_1, label_2 = data["labels"]
        for example, (labels_1, labels_2) in (
            (a, ([label_1], [label_2])),
            (b, ([label_1], [label_1])),
            (c, ([label_1], [label_2])),
        ):
            _label(batch, first, example, labels_1)
            _label(batch, second, example, labels_2)
        batch.set_phase(BatchPhase.DISCUSSION)
        assert self._rows(client, data) == [
            ("In discussion", None),
            ("Agreed", [label_1.name]),
            ("In discussion", None),
        ]

        discussed = BatchPhase.DISCUSSION
        _label(batch, first, a, [label_1], discussed)
        _label(batch, second, a, [label_1], discussed)
        _label(batch, first, c, [label_1], discussed)
        _label(batch, second, c, [label_2], discussed)
        assert self._rows(client, data) == [
            ("Agreed in discussion", [label_1.name]),
            ("Agreed", [label_1.name]),
            ("Disagree after discussion", None),
        ]

        batch.set_phase(BatchPhase.EXPERT)
        assert self._rows(client, data)[2] == ("Waiting for expert", None)
        _label(batch, data["expert"], c, [label_2], BatchPhase.EXPERT)
        assert self._rows(client, data)[2] == ("Expert decided", [label_2.name])

    def test_experts_who_decide_differently(self, client, batch_with_three):
        data = batch_with_three
        batch, (a, _b, _c) = data["batch"], data["examples"]
        first, second = data["annotators"]
        label_1, label_2 = data["labels"]
        other_expert = User.objects.create_user(username=f"x_{first.username}", password="123")
        ProjectUser.objects.create(
            project=data["project"], user=other_expert, default_role=ProjectRole.EXPERT
        )
        batch.users.add(other_expert, through_defaults={"role": ProjectRole.EXPERT})
        for example in data["examples"]:
            _label(batch, first, example, [label_1])
            _label(batch, second, example, [label_2])
        batch.set_phase(BatchPhase.DISCUSSION)
        for example in data["examples"]:
            _label(batch, first, example, [label_1], BatchPhase.DISCUSSION)
            _label(batch, second, example, [label_2], BatchPhase.DISCUSSION)
        batch.set_phase(BatchPhase.EXPERT)
        _label(batch, data["expert"], a, [label_1], BatchPhase.EXPERT)
        _label(batch, other_expert, a, [label_2], BatchPhase.EXPERT)

        assert self._rows(client, data)[0] == ("Experts disagree", None)

    def test_three_annotators(self, client, batch_with_three):
        data = batch_with_three
        batch, (a, _b, _c) = data["batch"], data["examples"]
        third = User.objects.create_user(username=f"t_{data['expert'].username}", password="123")
        ProjectUser.objects.create(
            project=data["project"], user=third, default_role=ProjectRole.ANNOTATOR
        )
        batch.users.add(third, through_defaults={"role": ProjectRole.ANNOTATOR})
        batch.set_phase(BatchPhase.ANNOTATION)  # assignments for the third annotator
        label_1, _label_2 = data["labels"]
        for annotator in data["annotators"]:
            _label(batch, annotator, a, [label_1])

        assert self._rows(client, data)[0] == ("Labeled 2 of 3", None)
        _label(batch, third, a, [label_1])
        assert self._rows(client, data)[0] == ("Agreed", [label_1.name])


@pytest.mark.django_db
class TestSamplePageCodebookChanges:
    """The sample's page shows the codebook changes saved with the decision on it."""

    def _page(self, client, data, example):
        _login(client, data["expert"])
        url = reverse("project-sample-detail", args=(example.batch_id, example.id))
        return client.get(url)

    def _change(self, data, rationale, **info):
        codebook = data["project"].codebook.get()
        version = len(codebook.changes()) + 1
        codebook.save(
            content=f"Version {version}",
            commit_message=json.dumps({"rationale": rationale, **info}),
        )

    def test_change_saved_with_the_decision(self, client, batch_with_three):
        data = batch_with_three
        a, b, _c = data["examples"]
        self._change(data, "Because of sample A.", example_id=a.id, text=a.content)
        self._change(data, "Because of sample B.", example_id=b.id, text=b.content)

        response = self._page(client, data, a)

        assert [c.rationale for c in response.context["changes"]] == ["Because of sample A."]
        content = " ".join(response.content.decode().split())
        assert "Codebook changed with this decision" in content
        assert "Because of sample A." in content

    def test_older_decisions_are_matched_by_text(self, client, batch_with_three):
        data = batch_with_three
        a, _b, _c = data["examples"]
        self._change(data, "Logged before the id was.", text=a.content)

        response = self._page(client, data, a)

        assert [c.rationale for c in response.context["changes"]] == ["Logged before the id was."]

    def test_same_text_in_another_sample_is_not_matched(self, client, batch_with_three):
        data = batch_with_three
        a, b, _c = data["examples"]
        Example.objects.filter(pk=b.pk).update(content=a.content)
        self._change(data, "Because of sample B.", example_id=b.id, text=a.content)

        response = self._page(client, data, a)

        assert response.context["changes"] == []
        assert "Codebook changed with this decision" not in response.content.decode()

    def test_status_and_label_on_the_page(self, client, batch_with_three):
        data = batch_with_three
        batch, (a, _b, _c) = data["batch"], data["examples"]
        label_1, _label_2 = data["labels"]
        for annotator in data["annotators"]:
            _label(batch, annotator, a, [label_1])

        response = self._page(client, data, a)

        assert response.context["state"]["status"] == "Agreed"
        section = response.content.decode().split('id="sample-state"')[1].split("</section>")[0]
        assert label_1.name in section
