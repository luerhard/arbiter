import io
import json
import re
import uuid

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
import pandas as pd
import pytest

from data.models import Example
from data.models import ExampleAssignment
from discuss.models import Message
from discuss.models import Room
from projects.models import Batch
from projects.models import BatchPhase
from projects.models import BatchUser
from projects.models import Project
from projects.models import ProjectRole
from projects.models import ProjectUser
from users.models import User

URLS_ANYROLE = [("project-list", None)]
URLS_EXPERT = [
    ("project-detail-expert", (1,)),
    ("project-export-batch", (1,)),
    ("project-export-project", (1,)),
]
URLS_ANNOTATOR = [("project-detail-annotator", (1,))]


@pytest.mark.django_db
class TestProjectListIndicators:
    def _project_row(self, content, project_name):
        # only look at the table; the sidebar lists the project names too
        table = content.split("<tbody", 1)[1]
        rows = [row for row in table.split("<tr") if project_name in row]
        assert rows, f"no project list row found for {project_name}"
        return rows[0]

    def test_open_annotation_badge_shown(self, client, project_annotation):
        # Regression: the list template referenced Project properties that did
        # not exist, so every project always rendered "Closed".
        annotator = project_annotation["annotators"][0]
        project = project_annotation["project"]
        client.login(username=annotator.username, password="123")

        response = client.get(reverse("project-list"))

        assert response.status_code == 200
        row = self._project_row(response.content.decode(), project.name)
        assert "Open" in row
        assert row.count("Closed") == 1  # discussion column stays closed

    def test_discussion_badge_shown_after_phase_change(self, client, project_discussion):
        annotator = project_discussion["annotators"][0]
        project = project_discussion["project"]
        client.login(username=annotator.username, password="123")

        response = client.get(reverse("project-list"))

        row = self._project_row(response.content.decode(), project.name)
        assert "Open" in row
        assert row.count("Closed") == 1  # annotation column now closed

    def test_finalized_annotator_is_not_offered_annotating(self, client, project_annotation):
        annotator = project_annotation["annotators"][0]
        batch = project_annotation["batch"]
        url = reverse("project-detail-annotator", args=(project_annotation["project"].id,))
        client.login(username=annotator.username, password="123")

        annotate_link = f'href="{reverse("annotate-batch", args=(batch.id,))}"'
        done_link = f'href="{reverse("annotate-done", args=(batch.id,))}"'

        content = client.get(url).content.decode()
        assert annotate_link in content

        BatchUser.objects.filter(batch=batch, user=annotator).update(finalized_at=timezone.now())
        content = client.get(url).content.decode()
        assert annotate_link not in content
        assert done_link in content

    def test_expert_page_counts_the_examples_to_discuss(self, client, project_discussion):
        # once the discussion started, its examples are fixed (DISCUSSION assignments);
        # a label changing afterwards must not change the counts on the batch card
        a1, a2 = project_discussion["annotators"]
        label1, _label2 = project_discussion["labels"]
        example = project_discussion["example"]
        ExampleAssignment.objects.get(
            user=a2,
            example=example,
            phase=BatchPhase.ANNOTATION,
        ).set_user_annotations([label1.id])
        for annotator in (a1, a2):  # the room saves both decisions together
            ExampleAssignment.objects.get(
                user=annotator,
                example=example,
                phase=BatchPhase.DISCUSSION,
            ).set_user_annotations([label1.id])
        client.login(username=project_discussion["expert"].username, password="123")

        response = client.get(
            reverse("project-detail-expert", args=(project_discussion["project"].id,)),
        )

        [card] = response.context["batches"]
        assert (card["disagreement"], card["discussed"]) == (1, 1)

    def test_active_batch_count_rendered(self, client, project_annotation):
        annotator = project_annotation["annotators"][0]
        project = project_annotation["project"]
        client.login(username=annotator.username, password="123")

        response = client.get(reverse("project-list"))

        row = self._project_row(response.content.decode(), project.name)
        assert f'<span class="font-mono">{project.annotator_n_active_batches}</span>' in row
        assert project.annotator_n_active_batches == 1


@pytest.mark.django_db
class TestProjectAndBatchCreationViews:
    def test_create_project_creates_project_users(self, client):
        suffix = uuid.uuid4().hex[:8]
        annotator_1 = User.objects.create_user(username=f"ann_{suffix}", password="123")
        annotator_2 = User.objects.create_user(username=f"ann2_{suffix}", password="123")
        expert = User.objects.create_user(username=f"exp_{suffix}", password="123")

        login = client.login(username="expert1", password="123")
        assert login == True

        url = reverse("project-create")
        data = {
            "name": f"Created Project {suffix}",
            "description": "Created in test",
            "annotators": [annotator_1.id, annotator_2.id],
            "experts": [expert.id],
            "label_name": ["Label A"],
            "label_color": ["#111111"],
            "label_hotkey": ["a"],
        }
        response = client.post(url, data)

        assert response.status_code == 302
        project = Project.objects.get(name=f"Created Project {suffix}")
        assert (
            ProjectUser.objects.filter(project=project, default_role=ProjectRole.ANNOTATOR).count()
            == 2
        )
        assert (
            ProjectUser.objects.filter(project=project, default_role=ProjectRole.EXPERT).count()
            == 1
        )

    def test_create_batch_creates_batch_and_assignments(self, client):
        suffix = uuid.uuid4().hex[:8]
        annotator_1 = User.objects.create_user(username=f"batch_ann_{suffix}", password="123")
        annotator_2 = User.objects.create_user(username=f"batch_ann2_{suffix}", password="123")
        expert = User.objects.create_user(username=f"batch_exp_{suffix}", password="123")

        project = Project.objects.create(
            name=f"Batch Project {suffix}",
            description="For batch test",
            owner=expert,
        )
        ProjectUser.objects.create(
            project=project,
            user=annotator_1,
            default_role=ProjectRole.ANNOTATOR,
        )
        ProjectUser.objects.create(
            project=project,
            user=annotator_2,
            default_role=ProjectRole.ANNOTATOR,
        )
        ProjectUser.objects.create(
            project=project,
            user=expert,
            default_role=ProjectRole.EXPERT,
        )

        login = client.login(username=expert.username, password="123")
        assert login == True

        upload = SimpleUploadedFile(
            "examples.csv",
            b"text\nFirst example\nSecond example\n",
            content_type="text/csv",
        )
        url = reverse("project-batch-create", args=(project.id,))
        response = client.post(
            url,
            {
                "file": upload,
                "annotators": [annotator_1.id, annotator_2.id],
                "experts": [expert.id],
            },
        )

        assert response.status_code == 302

        batch = Batch.objects.get(project=project)
        batch.set_phase(BatchPhase.ANNOTATION)
        example_assignments = ExampleAssignment.objects.filter(batch=batch)
        assert example_assignments.count() == 4
        assert set(example_assignments.values_list("user_id", flat=True)) == {
            annotator_1.id,
            annotator_2.id,
        }

    def test_batch_create_invalid_keeps_selected_users_context(self, client):
        suffix = uuid.uuid4().hex[:8]
        annotator = User.objects.create_user(username=f"batch_ann_ctx_{suffix}", password="123")
        expert = User.objects.create_user(username=f"batch_exp_ctx_{suffix}", password="123")

        project = Project.objects.create(
            name=f"Batch Project Context {suffix}",
            description="For batch context test",
            owner=expert,
        )
        ProjectUser.objects.create(
            project=project,
            user=annotator,
            default_role=ProjectRole.ANNOTATOR,
        )
        ProjectUser.objects.create(
            project=project,
            user=expert,
            default_role=ProjectRole.EXPERT,
        )

        login = client.login(username=expert.username, password="123")
        assert login == True

        url = reverse("project-batch-create", args=(project.id,))
        response = client.post(
            url,
            {
                # Deliberately omit file to keep the form invalid.
                "annotators": [annotator.id],
                "experts": [expert.id],
            },
        )

        assert response.status_code == 200
        assert response.context["annotators_selected_users"] == (
            f'[{{"id": {annotator.id}, "username": "{annotator.username}"}}]'
        )
        assert response.context["experts_selected_users"] == (
            f'[{{"id": {expert.id}, "username": "{expert.username}"}}]'
        )


@pytest.mark.django_db
class TestViews:
    @pytest.mark.parametrize("params", set(URLS_EXPERT + URLS_ANNOTATOR + URLS_ANYROLE))
    def test_login_required_not_logged_in(self, params, client):
        slug, args = params
        url = reverse(slug, args=args)
        req = client.get(url)
        assert req.status_code == 302

    @pytest.mark.parametrize("params", URLS_ANNOTATOR + URLS_ANYROLE)
    def test_http_200_as_annotator(self, params, client):
        slug, args = params
        url = reverse(slug, args=args)
        login = client.login(username="annotator1", password="123")
        assert login == True
        req = client.get(url)
        assert req.status_code == 200

    @pytest.mark.parametrize("params", URLS_EXPERT + URLS_ANYROLE)
    def test_http_200_as_expert(self, params, client):
        slug, args = params
        url = reverse(slug, args=args)
        login = client.login(username="expert1", password="123")
        assert login == True
        req = client.get(url)
        assert req.status_code == 200

    @pytest.mark.parametrize("params", URLS_ANNOTATOR)
    def test_annotator_page_open_to_expert(self, params, client):
        # the annotator page lists the user's own batches; roles are set per
        # batch, so experts may annotate too and need the page as well
        slug, args = params
        url = reverse(slug, args=args)
        login = client.login(username="expert1", password="123")
        assert login == True
        req = client.get(url)
        assert req.status_code == 200

    @pytest.mark.parametrize("params", URLS_EXPERT)
    def test_http_403_as_annotator(self, params, client):
        slug, args = params
        url = reverse(slug, args=args)
        login = client.login(username="annotator1", password="123")
        assert login == True
        req = client.get(url)
        assert req.status_code == 403

    def test_change_batch_phase_as_annotator(self, client):
        url = reverse("change-batch-phase", args=(1,))
        login = client.login(username="annotator1", password="123")
        assert login == True
        data = {"current_phase": "A"}
        req = client.post(url, data)
        assert req.status_code == 403

    def test_change_batch_phase_as_expert(self, client):
        url = reverse("change-batch-phase", args=(1,))
        login = client.login(username="expert1", password="123")
        assert login == True
        data = {"current_phase": "A"}
        req = client.post(url, data, HTTP_HX_REQUEST="true")  # the phase menu uses htmx
        assert req.status_code == 204

    def test_delete_batch_as_annotator(self, client):
        url = reverse("delete-batch", args=(1,))
        login = client.login(username="annotator1", password="123")
        assert login == True
        req = client.post(url)
        assert req.status_code == 403
        assert Batch.objects.filter(id=1).exists()

    def test_delete_batch_as_expert(self, client):
        url = reverse("delete-batch", args=(1,))
        login = client.login(username="expert1", password="123")
        assert login == True
        req = client.post(url)
        assert req.status_code == 302
        assert req.url == reverse("project-detail", args=(1,))
        assert not Batch.objects.filter(id=1).exists()

    def test_redirect_project_detail_expert(self, client):
        url = reverse("project-detail", args=(1,))
        login = client.login(username="expert1", password="123")
        req = client.get(url)
        assert req.status_code == 302
        assert req.url == reverse("project-detail-expert", args=(1,))

    def test_redirect_project_detail_annotator(self, client):
        url = reverse("project-detail", args=(1,))
        login = client.login(username="annotator1", password="123")
        req = client.get(url)
        assert req.status_code == 302
        assert req.url == reverse("project-detail-annotator", args=(1,))


@pytest.mark.django_db
def test_delete_batch_cascades_related_objects(client, project_annotation):
    data = project_annotation
    batch = data["batch"]
    expert = data["expert"]
    codebook = data["project"].codebook.get()
    tag = f"batch_{batch.batch_number}"
    assert ExampleAssignment.objects.filter(batch=batch).exists()
    assert tag in codebook.repo.tags

    login = client.login(username=expert.username, password="123")
    assert login is True

    resp = client.post(reverse("delete-batch", args=(batch.id,)))

    assert resp.status_code == 302
    assert not Batch.objects.filter(id=batch.id).exists()
    assert not ExampleAssignment.objects.filter(batch_id=batch.id).exists()
    assert tag not in codebook.repo.tags


@pytest.mark.django_db
def test_delete_batch_asks_for_confirmation(client, project_annotation):
    batch = project_annotation["batch"]
    client.login(username=project_annotation["expert"].username, password="123")

    content = client.get(
        reverse("project-detail-expert", args=(batch.project_id,))
    ).content.decode()

    assert f'commandfor="delete-batch-{batch.id}"' in content
    assert f'id="delete-batch-{batch.id}"' in content
    assert f'action="{reverse("delete-batch", args=(batch.id,))}"' in content
    assert re.search(r"its\s+1\s+sample:", content)
    assert "hx-confirm" not in content


@pytest.mark.django_db
class TestExportBatchView:
    ISO_WITH_MS_TZ_RE = re.compile(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}[+-]\d{2}:\d{2}$",
    )

    def test_export_batch_returns_expected_jsonl(self, client, project_annotation):
        data = project_annotation
        batch = data["batch"]
        example = data["example"]
        expert = data["expert"]
        annotator_1, annotator_2 = data["annotators"]
        label_1, label_2 = data["labels"]

        a1 = ExampleAssignment.objects.get(
            batch=batch,
            user=annotator_1,
            example=example,
            phase=BatchPhase.ANNOTATION,
        )
        a2 = ExampleAssignment.objects.get(
            batch=batch,
            user=annotator_2,
            example=example,
            phase=BatchPhase.ANNOTATION,
        )
        a1.set_user_annotations(label_ids=[label_1.id])
        a2.set_user_annotations(label_ids=[label_2.id])

        batch.set_phase(BatchPhase.DISCUSSION)
        d1 = ExampleAssignment.objects.get(
            batch=batch,
            user=annotator_1,
            example=example,
            phase=BatchPhase.DISCUSSION,
        )
        d2 = ExampleAssignment.objects.get(
            batch=batch,
            user=annotator_2,
            example=example,
            phase=BatchPhase.DISCUSSION,
        )
        d1.set_user_annotations(label_ids=[label_1.id])
        d2.set_user_annotations(label_ids=[label_2.id])

        batch.set_phase(BatchPhase.EXPERT)
        ex = ExampleAssignment.objects.get(
            batch=batch,
            user=expert,
            example=example,
            phase=BatchPhase.EXPERT,
        )
        ex.set_user_annotations(label_ids=[label_1.id])

        room = Room.objects.create()
        Message.objects.create(
            room=room,
            user=annotator_1.username,
            example=example,
            message="first message",
        )
        Message.objects.create(
            room=room,
            user=annotator_2.username,
            example=example,
            message="second message",
        )

        login = client.login(username=expert.username, password="123")
        assert login == True
        response = client.get(reverse("project-export-batch", args=(batch.id,)))

        assert response.status_code == 200
        assert response["Content-Disposition"] == (
            f"attachment; filename=batch_{batch.batch_number}.jsonl"
        )
        assert response["Content-Type"] == "application/text"

        lines = response.content.decode("utf-8").splitlines()
        assert len(lines) == 1

        row = json.loads(lines[0])
        assert row["text_id"] == example.id
        assert row["text"] == example.content
        assert row["batch_number"] == batch.batch_number
        assert row["batch_annotators"] == sorted([annotator_1.username, annotator_2.username])
        assert row["batch_experts"] == [expert.username]

        assert len(row["labels_annotation"]) == 2
        assert len(row["labels_discussion"]) == 2
        assert len(row["labels_expert"]) == 1

        for key in ["labels_annotation", "labels_discussion", "labels_expert"]:
            for entry in row[key]:
                assert set(entry.keys()) == {"user", "labels", "at"}
                assert self.ISO_WITH_MS_TZ_RE.match(entry["at"])

        assert len(row["messages_discussion"]) == 2
        assert row["messages_discussion"][0]["content"] == "first message"
        assert row["messages_discussion"][1]["content"] == "second message"
        for msg in row["messages_discussion"]:
            assert set(msg.keys()) == {"user", "at", "content"}
            assert self.ISO_WITH_MS_TZ_RE.match(msg["at"])

    def test_export_batch_includes_example_metadata(self, client, project_annotation):
        data = project_annotation
        batch, example = data["batch"], data["example"]
        example.metadata = {"id": 7, "source": "twitter"}
        example.save()
        assignment = ExampleAssignment.objects.get(
            batch=batch,
            user=data["annotators"][0],
            example=example,
            phase=BatchPhase.ANNOTATION,
        )
        assignment.set_user_annotations(label_ids=[data["labels"][0].id])

        client.login(username=data["expert"].username, password="123")
        response = client.get(reverse("project-export-batch", args=(batch.id,)))

        row = json.loads(response.content.decode("utf-8").splitlines()[0])
        assert row["metadata"] == {"id": 7, "source": "twitter"}

    def test_export_batch_lists_every_example_before_annotation(self, client, project_annotation):
        # A freshly uploaded batch exports its texts and metadata; only the labels are empty.
        data = project_annotation
        batch, example = data["batch"], data["example"]
        example.metadata = {"id": 7}
        example.save()

        client.login(username=data["expert"].username, password="123")
        response = client.get(reverse("project-export-batch", args=(batch.id,)))

        assert response.status_code == 200
        [line] = response.content.decode("utf-8").splitlines()
        row = json.loads(line)
        assert row["text_id"] == example.id
        assert row["text"] == example.content
        assert row["metadata"] == {"id": 7}
        assert row["batch_number"] == batch.batch_number
        for key in [
            "labels_annotation",
            "labels_discussion",
            "labels_expert",
            "messages_discussion",
        ]:
            assert row[key] == []

    def test_export_batch_includes_unannotated_examples_next_to_annotated(
        self,
        client,
        project_annotation,
    ):
        data = project_annotation
        batch, first = data["batch"], data["example"]
        second = Example.objects.create(batch=batch, content="Second", metadata={"id": 8})
        assignment = ExampleAssignment.objects.get(
            batch=batch,
            user=data["annotators"][0],
            example=first,
            phase=BatchPhase.ANNOTATION,
        )
        assignment.set_user_annotations(label_ids=[data["labels"][0].id])

        client.login(username=data["expert"].username, password="123")
        response = client.get(reverse("project-export-batch", args=(batch.id,)))

        rows = [json.loads(line) for line in response.content.decode("utf-8").splitlines()]
        assert [row["text_id"] for row in rows] == [first.id, second.id]
        assert len(rows[0]["labels_annotation"]) == 1
        assert rows[1]["labels_annotation"] == []
        assert rows[1]["metadata"] == {"id": 8}

    def test_export_project_without_batches_is_empty(self, client, project_annotation):
        # Regression: joining zero batches raised "No objects to concatenate".
        project = project_annotation["project"]
        project.batches.all().delete()
        client.login(username=project_annotation["expert"].username, password="123")

        response = client.get(reverse("project-export-project", args=(project.id,)))

        assert response.status_code == 200
        assert response.content.decode("utf-8").strip() == ""

    def test_export_project_returns_jsonl_with_slugified_filename(self, client, project_annotation):
        data = project_annotation
        batch = data["batch"]
        project = data["project"]
        expert = data["expert"]
        annotator = data["annotators"][0]
        label = data["labels"][0]
        example = data["example"]

        assignment = ExampleAssignment.objects.get(
            batch=batch,
            user=annotator,
            example=example,
            phase=BatchPhase.ANNOTATION,
        )
        assignment.set_user_annotations(label_ids=[label.id])

        project.name = "My Project 2026 !!!"
        project.save()

        login = client.login(username=expert.username, password="123")
        assert login == True
        response = client.get(reverse("project-export-project", args=(project.id,)))

        assert response.status_code == 200
        assert response["Content-Type"] == "application/text"
        assert response["Content-Disposition"] == (
            f"attachment; filename=project_{slugify(project.name)}.jsonl"
        )

        lines = response.content.decode("utf-8").splitlines()
        assert len(lines) == 1
        row = json.loads(lines[0])
        assert row["batch_number"] == batch.batch_number
        assert row["text_id"] == example.id
        assert row["labels_annotation"][0]["user"] == annotator.username


@pytest.mark.django_db
class TestPageHeader:
    def _breadcrumb(self, response):
        content = response.content.decode()
        return content.split('aria-label="Breadcrumb"', 1)[1].split("</nav>", 1)[0]

    def test_project_page_breadcrumb_ignores_codebook_in_context(self, client, project_annotation):
        # Regression: cotton components see the page context, so the view's
        # `codebook` variable added a "Codebook" crumb that nobody asked for.
        expert = project_annotation["expert"]
        project = project_annotation["project"]
        client.login(username=expert.username, password="123")

        response = client.get(reverse("project-detail-expert", args=(project.id,)))

        crumb = self._breadcrumb(response)
        assert project.name in crumb
        assert "Codebook" not in crumb

    def test_codebook_changes_breadcrumb_links_back_to_codebook(self, client, project_annotation):
        expert = project_annotation["expert"]
        codebook = project_annotation["project"].codebook.get()
        client.login(username=expert.username, password="123")

        response = client.get(reverse("codebook-diff", kwargs={"codebook_id": codebook.pk}))

        crumb = self._breadcrumb(response)
        assert reverse("codebook-view", args=(codebook.pk,)) in crumb
        assert "Changes" in crumb


@pytest.mark.django_db
class TestBatchUploadValidation:
    def _post(self, client, data, upload):
        client.login(username=data["expert"].username, password="123")
        return client.post(
            reverse("project-batch-create", args=(data["project"].id,)),
            {
                "file": upload,
                "annotators": [a.id for a in data["annotators"]],
                "experts": [data["expert"].id],
            },
        )

    def test_unsupported_file_type_shows_error(self, client, project_annotation):
        project = project_annotation["project"]
        batches_before = project.batches.count()
        upload = SimpleUploadedFile("examples.txt", b"text\nFirst\n", content_type="text/plain")

        response = self._post(client, project_annotation, upload)

        assert response.status_code == 200
        assert ".csv or .xlsx" in response.context["form"].errors["file"][0]
        assert project.batches.count() == batches_before

    def test_missing_text_column_shows_error(self, client, project_annotation):
        # Regression: the error was recorded but the batch was created anyway.
        project = project_annotation["project"]
        batches_before = project.batches.count()
        upload = SimpleUploadedFile("examples.csv", b"content\nFirst\n", content_type="text/csv")

        response = self._post(client, project_annotation, upload)

        assert response.status_code == 200
        assert "column named 'text'" in response.context["form"].errors["file"][0]
        assert project.batches.count() == batches_before

    def test_other_columns_are_stored_as_metadata(self, client, project_annotation):
        project = project_annotation["project"]
        upload = SimpleUploadedFile(
            "examples.csv",
            b"id,text,source,score\n7,First,twitter,0.5\n8,Second,,\n",
            content_type="text/csv",
        )

        response = self._post(client, project_annotation, upload)

        assert response.status_code == 302
        batch = project.batches.order_by("-batch_number").first()
        examples = list(batch.examples.order_by("pk"))
        assert [e.content for e in examples] == ["First", "Second"]
        assert examples[0].metadata == {"id": 7, "source": "twitter", "score": 0.5}
        # empty cells are stored as None, not as NaN
        assert examples[1].metadata == {"id": 8, "source": None, "score": None}

    def test_excel_upload_stores_metadata(self, client, project_annotation):
        # Regression: reading .xlsx needs openpyxl, which was not installed.
        project = project_annotation["project"]
        buffer = io.BytesIO()
        pd.DataFrame({"text": ["First"], "speaker": ["A"], "year": [2020]}).to_excel(
            buffer,
            index=False,
        )
        upload = SimpleUploadedFile("examples.xlsx", buffer.getvalue())

        response = self._post(client, project_annotation, upload)

        assert response.status_code == 302
        example = project.batches.order_by("-batch_number").first().examples.get()
        assert example.content == "First"
        assert example.metadata == {"speaker": "A", "year": 2020}

    def test_numeric_text_is_stored_as_text(self, client, project_annotation):
        project = project_annotation["project"]
        upload = SimpleUploadedFile("examples.csv", b"text\n123\n", content_type="text/csv")

        self._post(client, project_annotation, upload)

        example = project.batches.order_by("-batch_number").first().examples.get()
        assert example.content == "123"
        assert example.metadata == {}

    TEXTS_PANDAS_WOULD_CHANGE = ["NA", "None", "null", "#N/A", "nan", "007", "1.50", "true"]

    def test_texts_are_stored_exactly_as_written_in_csv(self, client, project_annotation):
        # Regression: "NA", "None" and the like were read as empty cells and rejected
        project = project_annotation["project"]
        rows = "".join(f"{i},{text},NA\n" for i, text in enumerate(self.TEXTS_PANDAS_WOULD_CHANGE))
        upload = SimpleUploadedFile(
            "examples.csv", f"id,text,region\n{rows}".encode(), content_type="text/csv"
        )

        response = self._post(client, project_annotation, upload)

        assert response.status_code == 302
        examples = list(project.batches.order_by("-batch_number").first().examples.order_by("pk"))
        assert [e.content for e in examples] == self.TEXTS_PANDAS_WOULD_CHANGE
        # the other columns are read as before
        assert examples[0].metadata == {"id": 0, "region": None}

    def test_texts_are_stored_exactly_as_written_in_excel(self, client, project_annotation):
        project = project_annotation["project"]
        # in Excel, #N/A is an error value, not a text (see the next test)
        texts = [text for text in self.TEXTS_PANDAS_WOULD_CHANGE if text != "#N/A"]
        buffer = io.BytesIO()
        pd.DataFrame({"text": texts}).to_excel(buffer, index=False)
        upload = SimpleUploadedFile("examples.xlsx", buffer.getvalue())

        response = self._post(client, project_annotation, upload)

        assert response.status_code == 302
        examples = project.batches.order_by("-batch_number").first().examples.order_by("pk")
        assert [e.content for e in examples] == texts

    def test_excel_error_cell_has_no_text(self, client, project_annotation):
        project = project_annotation["project"]
        batches_before = project.batches.count()
        buffer = io.BytesIO()
        pd.DataFrame({"text": ["First", "#N/A"]}).to_excel(buffer, index=False)
        upload = SimpleUploadedFile("examples.xlsx", buffer.getvalue())

        response = self._post(client, project_annotation, upload)

        assert "Row 3 has no text." in response.context["form"].errors["file"][0]
        assert project.batches.count() == batches_before

    def test_rows_without_text_are_rejected(self, client, project_annotation):
        # Regression: an empty text cell became an example with the text "nan".
        project = project_annotation["project"]
        batches_before = project.batches.count()
        upload = SimpleUploadedFile(
            "examples.csv",
            b"text,id\nFirst,1\n,2\n",
            content_type="text/csv",
        )

        response = self._post(client, project_annotation, upload)

        assert response.status_code == 200
        assert "Row 3" in response.context["form"].errors["file"][0]
        assert project.batches.count() == batches_before


@pytest.mark.django_db
class TestPhaseMenu:
    """Moving a batch on by hand while its phase is unfinished asks for confirmation."""

    def _card(self, client, data):
        client.login(username=data["expert"].username, password="123")
        response = client.get(reverse("project-detail-expert", args=(data["project"].id,)))
        [card] = response.context["batches"]
        confirm = {item["phase"] for item in card["phase_menu"] if item["confirm"]}
        return card, confirm, response.content.decode()

    def test_unlabeled_samples_need_confirmation_to_move_on(self, client, project_annotation):
        a1, a2 = project_annotation["annotators"]
        label1, _ = project_annotation["labels"]
        batch = project_annotation["batch"]
        ExampleAssignment.objects.get(user=a1, phase=BatchPhase.ANNOTATION).set_user_annotations(
            [label1.id]
        )

        card, confirm, content = self._card(client, project_annotation)

        # moving back leaves nothing open behind
        assert confirm == {BatchPhase.DISCUSSION, BatchPhase.EXPERT, BatchPhase.FINAL}
        assert card["open_work"].startswith(f"{a2.username} has 1 unlabeled sample.")
        assert a1.username not in card["open_work"]
        dialog = f'id="move-batch-{batch.id}-D"'
        assert dialog in content
        assert f'commandfor="move-batch-{batch.id}-D"' in content
        assert '<input type="hidden" name="current_phase" value="D"' in content

    def test_finished_annotation_moves_on_without_confirmation(self, client, project_annotation):
        label1, _ = project_annotation["labels"]
        for assignment in ExampleAssignment.objects.filter(phase=BatchPhase.ANNOTATION):
            assignment.set_user_annotations([label1.id])

        card, confirm, content = self._card(client, project_annotation)

        assert (card["open_work"], confirm) == ("", set())
        assert "move-batch-" not in content

    def test_open_discussion_needs_confirmation_to_move_on(self, client, project_discussion):
        card, confirm, _ = self._card(client, project_discussion)

        assert confirm == {BatchPhase.EXPERT, BatchPhase.FINAL}
        assert card["open_work"].startswith("1 of 1 disagreements is not discussed yet.")

    @pytest.mark.parametrize("htmx", [True, False], ids=["menu", "dialog"])
    def test_moving_the_batch(self, client, project_annotation, htmx):
        batch = project_annotation["batch"]
        client.login(username=project_annotation["expert"].username, password="123")
        headers = {"HTTP_HX_REQUEST": "true"} if htmx else {}

        response = client.post(
            reverse("change-batch-phase", args=(batch.id,)),
            {"current_phase": BatchPhase.DISCUSSION},
            **headers,
        )

        # the dialog posts a plain form: back to the project page instead of an empty page
        expected = 204 if htmx else 302
        assert response.status_code == expected
        batch.refresh_from_db()
        assert batch.current_phase == BatchPhase.DISCUSSION
