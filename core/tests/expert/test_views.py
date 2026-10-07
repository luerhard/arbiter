import json

from codebook.models import Codebook
from django.shortcuts import reverse
from expert.models import CodebookDraft
import pytest

from data.models import ExampleAssignment
from projects.models import BatchPhase


def _assignment_url(batch_id, assignment_id, **params):
    url = reverse("expert-assignment", args=[batch_id, assignment_id])
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    return url


@pytest.mark.django_db
class TestExpertNavigation:
    @pytest.fixture(autouse=True)
    def setup(self, client, project_expert):
        self.client = client
        self.data = project_expert
        self.batch = self.data["batch"]
        self.client.login(username=self.data["expert"].username, password="123")
        self.assignment = (
            ExampleAssignment.objects.filter(
                batch=self.batch,
                user=self.data["expert"],
                phase=BatchPhase.EXPERT,
            )
            .order_by("order", "id")
            .first()
        )

    def test_batch_entry_redirects_to_first_open_assignment(self):
        response = self.client.get(reverse("expert-batch", args=[self.batch.id]))
        assert response.status_code == 302
        assert response.url == _assignment_url(self.batch.id, self.assignment.id)

    def test_batch_entry_redirects_to_review_when_all_done(self):
        self.assignment.set_user_annotations([self.data["labels"][0].id])
        response = self.client.get(reverse("expert-batch", args=[self.batch.id]))
        assert response.status_code == 302
        assert response.url == _assignment_url(self.batch.id, self.assignment.id)
        page = self.client.get(response.url)
        assert page.status_code == 200
        assert page.context["review"] is True

    def test_assignment_full_page_render(self):
        response = self.client.get(_assignment_url(self.batch.id, self.assignment.id))
        assert response.status_code == 200
        assert "expert/index.html" in (t.name for t in response.templates)
        assert response.context["assignment"] == self.assignment
        assert response.context["sentence"] == self.data["example"]
        assert response.context["review"] is False

    def test_assignment_htmx_returns_partial(self):
        response = self.client.get(
            _assignment_url(self.batch.id, self.assignment.id),
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        assert "expert/partials/assignment.html" in (t.name for t in response.templates)
        assert b"<html" not in response.content

    def test_foreign_assignment_is_forbidden_not_500(self, client):
        # Another expert's assignment id under this batch URL -> 403.
        other_login = client.login(username=self.data["annotators"][0].username, password="123")
        assert other_login is True
        response = client.get(_assignment_url(self.batch.id, self.assignment.id))
        assert response.status_code == 403

    def test_assignment_from_other_batch_forbidden(self):
        annotation_assignment = ExampleAssignment.objects.filter(
            batch=self.batch,
            phase=BatchPhase.ANNOTATION,
        ).first()
        response = self.client.get(
            _assignment_url(self.batch.id, annotation_assignment.id),
        )
        assert response.status_code == 403

    def test_dialogue_renders_without_annotation_phase_assignments(self):
        # Regression: StopIteration crash when picking the chat-alignment
        # annotator for an example without annotation-phase assignments.
        ExampleAssignment.objects.filter(
            example=self.data["example"],
            phase=BatchPhase.ANNOTATION,
        ).delete()
        response = self.client.get(_assignment_url(self.batch.id, self.assignment.id))
        assert response.status_code == 200
        assert response.context["annotator"] is None

    def test_label_checkboxes_use_form_field_name(self):
        # Regression: rendered checkboxes must POST under the name the form
        # reads; a mismatch silently drops every selection.
        response = self.client.get(_assignment_url(self.batch.id, self.assignment.id))
        content = response.content.decode()
        html_name = response.context["labels_form"]["labels"].html_name
        assert content.count(f'name="{html_name}"') >= len(self.data["labels"])
        # Pre-selected are the labels both annotators kept after the discussion
        # (label 1), not the contested one (label 2, only the second annotator).
        initial = response.context["labels_form"].fields["labels"].initial
        assert initial == [self.data["labels"][0].id]
        assert "checked" in content


@pytest.mark.django_db
class TestExpertDecision:
    @pytest.fixture(autouse=True)
    def setup(self, client, project_expert):
        self.client = client
        self.data = project_expert
        self.batch = self.data["batch"]
        self.client.login(username=self.data["expert"].username, password="123")
        self.assignment = (
            ExampleAssignment.objects.filter(
                batch=self.batch,
                user=self.data["expert"],
                phase=BatchPhase.EXPERT,
            )
            .order_by("order", "id")
            .first()
        )
        self.codebook = Codebook.objects.filter(project=self.data["project"]).first()
        self.url = _assignment_url(self.batch.id, self.assignment.id)

    def _post_labels(self, label_ids, htmx=True, **extra):
        kwargs = {"HTTP_HX_REQUEST": "true"} if htmx else {}
        return self.client.post(self.url, data={"labels": label_ids, **extra}, **kwargs)

    def test_multiple_labels_saved(self):
        label_ids = [label.id for label in self.data["labels"]]
        response = self._post_labels(label_ids, htmx=False)
        assert response.status_code == 302
        self.assignment.refresh_from_db()
        assert self.assignment.done is not None
        assert sorted(self.assignment.annotations.values_list("label_id", flat=True)) == sorted(
            label_ids,
        )

    def test_single_label_saved(self):
        label = self.data["labels"][0]
        response = self._post_labels([label.id], htmx=False)
        assert response.status_code == 302
        self.assignment.refresh_from_db()
        assert list(self.assignment.annotations.values_list("label_id", flat=True)) == [label.id]

    def test_zero_labels_is_valid_decision(self):
        # Zero labels is a valid verdict ("non-offensive" under multi-label).
        response = self.client.post(self.url, data={})
        assert response.status_code == 302
        self.assignment.refresh_from_db()
        assert self.assignment.done is not None
        assert self.assignment.annotations.count() == 0

    def test_invalid_label_id_saves_nothing(self):
        response = self._post_labels([9999])
        assert response.status_code == 200
        trigger = json.loads(response["HX-Trigger"])
        assert any("Something was invalid" in m["message"] for m in trigger["messages"])
        self.assignment.refresh_from_db()
        assert self.assignment.done is None
        assert self.assignment.annotations.count() == 0

    def test_htmx_save_advances_and_pushes_url(self):
        label = self.data["labels"][0]
        response = self._post_labels([label.id])
        assert response.status_code == 200
        # Single-example fixture: everything resolved after this save.
        assert response.context["assignment"] is None
        assert response["HX-Push-Url"] == reverse("expert-batch", args=[self.batch.id])
        trigger = json.loads(response["HX-Trigger"])
        assert any(m["message"] == "Saved." for m in trigger["messages"])

    def test_last_decision_finalizes_batch(self):
        self._post_labels([self.data["labels"][0].id])
        self.batch.refresh_from_db()
        assert self.batch.current_phase == BatchPhase.FINAL

    def test_stale_resubmit_is_rejected_with_409(self):
        # A leftover tab must not silently overwrite a saved decision.
        label1, label2 = self.data["labels"]
        self.assignment.set_user_annotations([label1.id])

        response = self._post_labels([label2.id])

        assert response.status_code == 409
        trigger = json.loads(response["HX-Trigger"])
        assert any("already saved" in m["message"] for m in trigger["messages"])
        self.assignment.refresh_from_db()
        assert list(self.assignment.annotations.values_list("label_id", flat=True)) == [label1.id]

    def test_review_mode_shows_decision_and_edit_button(self):
        label = self.data["labels"][0]
        self.assignment.set_user_annotations([label.id])

        response = self.client.get(self.url)

        assert response.status_code == 200
        assert response.context["review"] is True
        assert [a.label_id for a in response.context["decision_annotations"]] == [label.id]
        assert b"Edit decision" in response.content

    def test_edit_flow_revises_decision_with_empty_commit(self):
        # Corrections append a revision entry to the codebook log; the
        # original commit is never rewritten.
        label1, label2 = self.data["labels"]
        self.assignment.set_user_annotations([label1.id])
        commits_before = len(list(self.codebook.repo.iter_commits()))

        edit_page = self.client.get(self.url + "?edit=1")
        assert edit_page.status_code == 200
        assert edit_page.context["review"] is False
        # Editing pre-selects the saved decision, not the discussion union.
        assert edit_page.context["labels_form"].fields["labels"].initial == [label1.id]

        response = self.client.post(self.url, data={"labels": [label2.id], "edit": "1"})
        assert response.status_code == 302
        assert response.url == _assignment_url(self.batch.id, self.assignment.id)

        self.assignment.refresh_from_db()
        assert list(self.assignment.annotations.values_list("label_id", flat=True)) == [label2.id]

        commits = list(self.codebook.repo.iter_commits())
        assert len(commits) == commits_before + 1
        revision = json.loads(commits[0].message)
        assert revision["revises"] is True
        assert revision["previous_decision"] == [label1.name]
        assert revision["final_decision"] == [label2.name]


@pytest.mark.django_db
class TestCodebookDraft:
    @pytest.fixture(autouse=True)
    def setup(self, client, project_expert):
        self.client = client
        self.data = project_expert
        self.batch = self.data["batch"]
        self.client.login(username=self.data["expert"].username, password="123")
        self.assignment = (
            ExampleAssignment.objects.filter(
                batch=self.batch,
                user=self.data["expert"],
                phase=BatchPhase.EXPERT,
            )
            .order_by("order", "id")
            .first()
        )
        self.codebook = Codebook.objects.filter(project=self.data["project"]).first()
        # Give the fixture codebook real content; a pristine codebook is
        # empty, which would trip the cannot-be-emptied guard instead of the
        # branches under test.
        self.codebook.save(
            content="# Codebook\n\nBaseline rules.\n",
            commit_message="baseline",
        )
        self.draft_url = reverse("expert-draft-save", args=[self.batch.id, self.assignment.id])
        self.delete_url = reverse("expert-draft-delete", args=[self.batch.id, self.assignment.id])
        self.panel_url = reverse("expert-codebook-panel", args=[self.batch.id, self.assignment.id])
        self.decision_url = _assignment_url(self.batch.id, self.assignment.id)

    def _save_draft(self, content, rationale=""):
        return self.client.post(
            self.draft_url,
            data={"content": content, "rationale": rationale},
            HTTP_HX_REQUEST="true",
        )

    def test_draft_saved_and_shown_in_panel(self):
        new_content = self.codebook.content + "\n# New edge case"
        response = self._save_draft(new_content, rationale="found an edge case")

        assert response.status_code == 200
        draft = CodebookDraft.objects.get(assignment=self.assignment)
        assert "# New edge case" in draft.content
        assert draft.rationale == "found an edge case"
        assert draft.base_revision == self.codebook.repo.head.commit.hexsha
        assert b"Uncommitted draft" in response.content
        # Codebook itself is untouched until the decision commits.
        assert "# New edge case" not in self.codebook.content

    def test_draft_survives_reload(self):
        new_content = self.codebook.content + "\n# Persistent edit"
        self._save_draft(new_content, rationale="why")

        page = self.client.get(self.decision_url)
        assert b"Persistent edit" in page.content
        assert b"Uncommitted draft" in page.content

    def test_unchanged_content_discards_draft(self):
        self._save_draft(self.codebook.content + "\n# temp", rationale="x")
        assert CodebookDraft.objects.filter(assignment=self.assignment).exists()

        self._save_draft(self.codebook.content)
        assert not CodebookDraft.objects.filter(assignment=self.assignment).exists()

    def test_crlf_only_difference_is_not_a_draft(self):
        crlf = "\r\n".join(self.codebook.content.splitlines())
        self._save_draft(crlf)
        assert not CodebookDraft.objects.filter(assignment=self.assignment).exists()

    def test_undo_deletes_draft(self):
        self._save_draft(self.codebook.content + "\n# doomed", rationale="x")
        response = self.client.post(self.delete_url)
        assert response.status_code == 200
        assert not CodebookDraft.objects.filter(assignment=self.assignment).exists()
        assert b"Uncommitted draft" not in response.content

    def test_empty_content_rejected(self):
        response = self._save_draft("   \n  ")
        assert response.status_code == 200
        assert not CodebookDraft.objects.filter(assignment=self.assignment).exists()
        trigger = json.loads(response["HX-Trigger"])
        assert any("cannot be emptied" in m["message"] for m in trigger["messages"])

    def test_panel_edit_mode(self):
        response = self.client.get(self.panel_url + "?mode=edit")
        assert response.status_code == 200
        assert b'name="content"' in response.content
        assert b'name="rationale"' in response.content

    def test_decision_commits_draft_with_metadata(self):
        new_content = self.codebook.content + "\n# Committed edge case"
        self._save_draft(new_content, rationale="documented the edge case")
        label_ids = [label.id for label in self.data["labels"]]

        response = self.client.post(self.decision_url, data={"labels": label_ids})

        assert response.status_code == 302
        self.codebook.refresh_from_db()
        assert "# Committed edge case" in self.codebook.content
        assert not CodebookDraft.objects.filter(assignment=self.assignment).exists()

        commit = json.loads(self.codebook.repo.head.commit.message)
        assert commit["rationale"] == "documented the edge case"
        assert sorted(commit["final_decision"]) == sorted(
            label.name for label in self.data["labels"]
        )
        assert commit["text"] == self.data["example"].content
        assert "labels_before_discussion" in commit
        assert "labels_after_discussion" in commit
        assert "chat_history" in commit

    def test_draft_without_rationale_is_refused_and_kept_in_the_editor(self):
        typed = self.codebook.content + "\n# needs rationale"

        response = self._save_draft(typed, rationale="  ")

        assert response.status_code == 200
        assert not CodebookDraft.objects.filter(assignment=self.assignment).exists()
        content = response.content.decode()
        assert 'id="rationale-error"' in content
        assert "# needs rationale" in content  # still in the editor
        assert 'name="rationale"' in content

    def test_draft_rationale_stays_when_editing_again(self):
        self._save_draft(self.codebook.content + "\n# edit", rationale="my reason")

        response = self.client.get(self.panel_url + "?mode=edit")

        assert "my reason" in response.content.decode()

    def test_decision_without_rationale_is_rejected_not_dropped(self):
        # A codebook change without rationale must fail loudly and save
        # nothing -- never silently discard the edit (the bug users hit).
        # Saving such a draft is refused; this guards drafts from before that.
        original = self.codebook.content
        CodebookDraft.objects.create(
            assignment=self.assignment,
            content=original + "\n# needs rationale",
            rationale="",
            base_revision=self.codebook.repo.head.commit.hexsha,
        )

        response = self.client.post(
            self.decision_url,
            data={"labels": [self.data["labels"][0].id]},
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        trigger = json.loads(response["HX-Trigger"])
        assert any("rationale is required" in m["message"] for m in trigger["messages"])
        self.assignment.refresh_from_db()
        assert self.assignment.done is None
        assert self.assignment.annotations.count() == 0
        self.codebook.refresh_from_db()
        assert self.codebook.content == original
        # The draft survives the rejection.
        assert CodebookDraft.objects.filter(assignment=self.assignment).exists()

    def test_conflicting_codebook_revision_blocks_commit(self):
        # Optimistic lock: the codebook moved on after the draft was started.
        self._save_draft(self.codebook.content + "\n# based on old revision", rationale="x")
        self.codebook.save(
            content=self.codebook.content + "\n# concurrent change",
            commit_message="concurrent",
        )

        response = self.client.post(
            self.decision_url,
            data={"labels": [self.data["labels"][0].id]},
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        trigger = json.loads(response["HX-Trigger"])
        assert any("changed since" in m["message"] for m in trigger["messages"])
        self.assignment.refresh_from_db()
        assert self.assignment.done is None
        assert "# based on old revision" not in self.codebook.content
        assert CodebookDraft.objects.filter(assignment=self.assignment).exists()

    def test_corrected_decision_does_not_block_a_draft(self):
        # correcting another decision logs a commit, but the codebook text is the same
        self._save_draft(self.codebook.content + "\n# my edit", rationale="why")
        self.codebook.commit_decision_revision(json.dumps({"rationale": "", "revises": True}))

        response = self.client.post(self.decision_url, data={"labels": [self.data["labels"][0].id]})

        assert response.status_code == 302
        self.codebook.refresh_from_db()
        assert "# my edit" in self.codebook.content
        assert not CodebookDraft.objects.filter(assignment=self.assignment).exists()

    def test_decision_without_draft_commits_nothing(self):
        commits_before = len(list(self.codebook.repo.iter_commits()))
        self.client.post(self.decision_url, data={"labels": [self.data["labels"][0].id]})
        assert len(list(self.codebook.repo.iter_commits())) == commits_before
