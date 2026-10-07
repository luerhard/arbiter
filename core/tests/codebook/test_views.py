import io
import json
import zipfile

from codebook.models import Codebook
from django.contrib.auth import get_user_model
from django.urls import reverse
import pytest

from data.models import Example
from projects.models import Batch
from projects.models import BatchPhase
from projects.models import Project
from projects.models import ProjectRole
from projects.models import ProjectUser

User = get_user_model()


def _text(response):
    """The page with whitespace collapsed: templates wrap text across lines."""
    return " ".join(response.content.decode().split())


URLS_EXPERT = [("codebook-view", (1,)), ("codebook-diff", (1,)), ("codebook-edit", (1,))]

URLS_ANNOTATOR = [("codebook-view", (1,)), ("codebook-diff", (1,))]


@pytest.fixture
def project_setup():
    return {
        "project": Project.objects.first(),
        "batch": Batch.objects.first(),
        "codebook": Codebook.objects.first(),
    }


@pytest.mark.django_db
class TestViews:
    @pytest.mark.parametrize("params", set(URLS_EXPERT + URLS_ANNOTATOR))
    def test_login_required_not_logged_in(self, params, client):
        slug, args = params
        url = reverse(slug, args=args)
        req = client.get(url)
        assert req.status_code == 302

    @pytest.mark.parametrize("params", URLS_ANNOTATOR)
    def test_http_200_as_annotator(self, params, client):
        slug, args = params
        url = reverse(slug, args=args)
        login = client.login(username="annotator1", password="123")
        assert login == True
        req = client.get(url)
        assert req.status_code == 200

    @pytest.mark.parametrize("params", URLS_EXPERT)
    def test_http_200_as_expert(self, params, client):
        slug, args = params
        url = reverse(slug, args=args)
        login = client.login(username="expert1", password="123")
        assert login == True
        req = client.get(url)
        assert req.status_code == 200

    @pytest.mark.parametrize("params", [("codebook-edit", (1,))])
    def test_codebook_update_view_annotator_access_denied(self, params, client):
        slug, args = params
        url = reverse(slug, args=args)
        login = client.login(username="annotator1", password="123")
        assert login == True
        req = client.get(url)
        assert req.status_code == 403

    @pytest.mark.parametrize("params", URLS_EXPERT)
    def test_codebook_update_view_post_all_data(self, params, client, project_setup):
        login = client.login(username="expert1", password="123")
        assert login is True

        codebook = project_setup["codebook"]

        new_content = "Updated codebook content test 1."
        post_data = {
            "content": new_content,
            "rationale": "Test rationale",
        }
        response = client.post(reverse("codebook-edit", args=[codebook.id]), post_data)

        assert response.status_code == 302
        assert response.url == codebook.get_absolute_url()

        codebook.refresh_from_db()
        assert codebook.content == new_content + "\n"

    def test_codebook_export_not_logged_in(self, client):
        url = reverse("codebook-export", args=(1,))
        req = client.get(url)
        assert req.status_code == 302

    def test_codebook_export_annotator_access_denied(self, client):
        url = reverse("codebook-export", args=(1,))
        login = client.login(username="annotator1", password="123")
        assert login is True
        req = client.get(url)
        assert req.status_code == 403

    def test_codebook_export_as_expert(self, client):
        url = reverse("codebook-export", args=(1,))
        login = client.login(username="expert1", password="123")
        assert login is True
        req = client.get(url)

        assert req.status_code == 200
        assert req["Content-Type"] == "application/zip"
        assert "attachment" in req["Content-Disposition"]
        assert req["Content-Disposition"].endswith(".zip")

        with zipfile.ZipFile(io.BytesIO(req.content)) as zf:
            assert zf.testzip() is None
            names = zf.namelist()
            assert "main.md" in names
            assert any(name.startswith(".git/") for name in names)

    @pytest.mark.parametrize("params", URLS_EXPERT)
    def test_codebook_update_view_post_some_data(self, params, client, project_setup):
        login = client.login(username="expert1", password="123")
        assert login is True

        codebook = project_setup["codebook"]

        new_content = "Updated codebook content test 2."
        post_data = {
            "content": new_content,
            "rationale": "Test rationale",
        }
        response = client.post(reverse("codebook-edit", args=[codebook.id]), post_data)

        assert response.status_code == 302
        assert response.url == codebook.get_absolute_url()

        codebook.refresh_from_db()
        assert codebook.content == new_content + "\n"


@pytest.mark.django_db
class TestDiffAfterBatchDeletion:
    """Deleting a batch removes its codebook tag; the next batch's diff must still work."""

    def _diff(self, client, codebook, old, new):
        return client.get(
            reverse("codebook-diff", args=(codebook.pk,)), {"batch_old": old, "batch_new": new}
        )

    def test_compares_with_the_batch_before_the_deleted_one(self, client, project_annotation):
        codebook = project_annotation["project"].codebook.get()
        for number in (2, 3):
            codebook.save(content=f"Version {number}\n", commit_message=f"Batch {number}")
            codebook.tag_version(number)
        codebook.untag_version(2)
        client.login(username=project_annotation["expert"].username, password="123")

        response = self._diff(client, codebook, 2, 3)

        assert response.status_code == 200
        assert response.context["batch_old"] == 1
        assert "Version 3" in response.context["content_diff"]

    def test_deleted_batch_has_no_diff(self, client, project_annotation):
        codebook = project_annotation["project"].codebook.get()
        client.login(username=project_annotation["expert"].username, password="123")

        response = self._diff(client, codebook, 1, 2)

        assert response.status_code == 404


@pytest.mark.django_db
class TestCodebookHistory:
    """Every change of the codebook text is listed with its rationale; a batch shows the
    changes made since the previous batch started."""

    @pytest.fixture(autouse=True)
    def setup(self, client, project_annotation):
        self.client = client
        self.data = project_annotation
        self.codebook = project_annotation["project"].codebook.get()

    def _edit(self, content, rationale):
        self.client.login(username=self.data["expert"].username, password="123")
        response = self.client.post(
            reverse("codebook-edit", args=[self.codebook.pk]),
            {"content": content, "rationale": rationale},
        )
        assert response.status_code == 302

    def test_history_lists_each_change_with_its_rationale(self):
        self._edit("Version 1", "The first version.")
        self.codebook.tag_version(1)
        self._edit("Version 2", "Sarcasm counts as negative.")

        self.client.login(username=self.data["annotators"][0].username, password="123")
        response = self.client.get(reverse("codebook-view", args=[self.codebook.pk]))

        changes = response.context["changes"]
        assert [(c.rationale, c.when) for c in changes] == [
            ("Sarcasm counts as negative.", "during batch 1"),
            ("The first version.", "before batch 1"),
        ]
        content = response.content.decode()
        assert "Sarcasm counts as negative." in content
        assert reverse("codebook-change", args=[self.codebook.pk, changes[0].sha]) in content

    def test_history_says_during_which_batch_a_change_was_made(self):
        self._edit("Version 1", "First.")
        self.codebook.tag_version(1)
        self._edit("Version 2", "Changed while batch 1 ran.")
        self.codebook.tag_version(2)

        assert [c.when for c in self.codebook.changes()] == ["during batch 1", "before batch 1"]

    def test_history_without_changes(self):
        self.client.login(username=self.data["expert"].username, password="123")
        response = self.client.get(reverse("codebook-view", args=[self.codebook.pk]))

        assert response.context["changes"] == []
        assert "No changes yet." in response.content.decode()

    def test_change_saved_with_an_expert_decision_names_the_sample(self):
        info = {"rationale": "See this case.", "text": "A sample text", "final_decision": []}
        self.codebook.save(content="Version 1", commit_message=json.dumps(info))

        (change,) = self.codebook.changes()
        assert (change.rationale, change.decision_text) == ("See this case.", "A sample text")

    def test_change_page_shows_what_one_change_changed(self):
        self._edit("Version one", "First.")
        self._edit("Version two", "Renamed.")
        newest = self.codebook.changes()[0]

        self.client.login(username=self.data["annotators"][0].username, password="123")
        response = self.client.get(reverse("codebook-change", args=[self.codebook.pk, newest.sha]))

        assert response.status_code == 200
        assert response.context["content_diff"] == "Version [-one-]{+two+}"
        assert "Renamed." in response.content.decode()

    @pytest.mark.parametrize("sha", ["0" * 40, "HEAD", "--output=x"])
    def test_change_page_only_for_changes_of_this_codebook(self, sha):
        self._edit("Version 1", "First.")
        self.client.login(username=self.data["expert"].username, password="123")

        response = self.client.get(reverse("codebook-change", args=[self.codebook.pk, sha]))

        assert response.status_code == 404

    def _batch(self, *annotators):
        """A new batch that starts annotation now, which keeps the current codebook."""
        batch = Batch.objects.create(project=self.data["project"])
        batch.users.add(*annotators, through_defaults={"role": ProjectRole.ANNOTATOR})
        Example.objects.create(batch=batch, content="Example")
        batch.set_phase(BatchPhase.ANNOTATION)
        return batch

    def _annotation_page(self, user, batch):
        self.client.login(username=user.username, password="123")
        response = self.client.get(reverse("annotate-batch", args=[batch.id]), follow=True)
        assert response.status_code == 200
        return response.context

    def test_annotators_see_every_change_since_their_last_batch(self):
        # lena annotated batch 1, skipped batch 2 and is now in batch 3: she sees what
        # changed during batches 1 and 2, and what changed during batch 3
        lena, jonas = self.data["annotators"]
        self._edit("Version 1", "First.")
        self.codebook.tag_version(1)  # batch 1 of the fixture, lena and jonas
        self._edit("Version 2", "Changed during batch 1.")
        self._batch(jonas)  # batch 2
        self._edit("Version 3", "Changed during batch 2.")
        batch3 = self._batch(lena)
        self._edit("Version 4", "Changed during batch 3.")

        context = self._annotation_page(lena, batch3)

        assert context["codebook_since"] == 1
        assert context["content_diff"] == "Version [-1-]{+4+}"
        assert [c.rationale for c in context["codebook_changes"]] == [
            "Changed during batch 3.",
            "Changed during batch 2.",
            "Changed during batch 1.",
        ]

    def test_annotation_page_names_the_batch_the_changes_are_since(self):
        lena, _jonas = self.data["annotators"]
        self._edit("Version 1", "First.")
        self.codebook.tag_version(1)
        self._edit("Version 2", "Second.")
        batch2 = self._batch(lena)
        self.client.login(username=lena.username, password="123")

        response = self.client.get(reverse("annotate-batch", args=[batch2.id]), follow=True)

        content = _text(response)
        assert "Changes since batch 1" in content
        assert "Second." in content

    def test_first_batch_of_an_annotator_shows_the_changes_since_it_started(self):
        # what came before is new to them anyway: they read the codebook
        _lena, jonas = self.data["annotators"]
        self._edit("Version 1", "First.")
        self.codebook.tag_version(1)
        self._edit("Version 2", "Second.")
        newcomer = User.objects.create_user(username=f"new_{jonas.username}", password="123")
        ProjectUser.objects.create(
            project=self.data["project"], user=newcomer, default_role=ProjectRole.ANNOTATOR
        )
        batch2 = self._batch(newcomer)

        context = self._annotation_page(newcomer, batch2)
        assert (context["codebook_since"], context["content_diff"]) == (2, "")

        self._edit("Version 3", "Changed while they annotate.")
        context = self._annotation_page(newcomer, batch2)
        assert context["content_diff"] == "Version [-2-]{+3+}"
        assert [c.rationale for c in context["codebook_changes"]] == [
            "Changed while they annotate."
        ]

    def test_no_changes_against_an_empty_codebook(self):
        # batch 1 started before anything was written: all of it would be new
        self._edit("Version 1", "First.")

        assert self.codebook.get_as_context(1)["content_diff"] == ""

    def test_no_changes_since_the_last_batch(self):
        lena, _jonas = self.data["annotators"]
        self._edit("Version 1", "First.")
        self.codebook.tag_version(1)
        batch2 = self._batch(lena)

        context = self._annotation_page(lena, batch2)

        assert (context["codebook_since"], context["content_diff"]) == (1, "")

    def test_last_batch_skips_a_deleted_batch(self):
        lena, _jonas = self.data["annotators"]
        self._edit("Version 1", "First.")
        self.codebook.tag_version(1)
        batch2 = self._batch(lena)
        batch3 = self._batch(lena)
        self.codebook.untag_version(batch2.batch_number)
        batch2.delete()

        assert self.codebook.last_batch_of(lena, before=batch3.batch_number) == 1

    def test_discussion_shows_the_changes_since_the_batch_started(self):
        self._edit("Version 1", "First.")
        self.codebook.tag_version(1)
        self._edit("Version 2", "Changed during the batch.")

        context = self.codebook.get_as_context(1)

        assert context["content_diff"] == "Version [-1-]{+2+}"
        assert [c.rationale for c in context["codebook_changes"]] == ["Changed during the batch."]

    def test_codebook_page_links_the_changes_since_the_readers_last_batch(self):
        lena, _jonas = self.data["annotators"]
        self._edit("Version 1", "First.")
        self.codebook.tag_version(1)
        self._batch(self.data["annotators"][1])  # batch 2, without lena
        self._edit("Version 2", "Second.")
        url = reverse("codebook-view", args=[self.codebook.pk])

        self.client.login(username=lena.username, password="123")
        assert self.client.get(url).context["since"] == 1
        # an expert annotates in no batch: since the newest batch started
        self.client.login(username=self.data["expert"].username, password="123")
        response = self.client.get(url)
        assert response.context["since"] == 2
        assert "Changes since batch 2" in _text(response)

    def test_diff_page_defaults_to_the_changes_since_the_readers_last_batch(self):
        lena, _jonas = self.data["annotators"]
        self._edit("Version 1", "First.")
        self.codebook.tag_version(1)
        self._edit("Version 2", "Second.")
        self.client.login(username=lena.username, password="123")

        response = self.client.get(reverse("codebook-diff", args=(self.codebook.pk,)))

        assert (response.context["batch_old"], response.context["batch_new"]) == (1, None)
        assert response.context["content_diff"] == "Version [-1-]{+2+}"
        assert "since batch 1 started" in _text(response)

    def test_diff_page_refuses_a_bad_batch_number(self):
        self.client.login(username=self.data["expert"].username, password="123")

        response = self.client.get(
            reverse("codebook-diff", args=(self.codebook.pk,)), {"batch_old": "x"}
        )

        assert response.status_code == 404

    def test_diff_page_without_changes(self):
        self._edit("Version 1", "First.")
        self.codebook.tag_version(1)
        self.codebook.tag_version(2)
        self.client.login(username=self.data["expert"].username, password="123")

        response = self.client.get(
            reverse("codebook-diff", args=(self.codebook.pk,)), {"batch_old": 1, "batch_new": 2}
        )

        assert response.status_code == 200
        assert response.context["content_diff"] == ""
        assert "No changes" in response.content.decode()

    def test_diff_page_lists_the_rationales(self):
        self._edit("Version one", "First.")
        self.codebook.tag_version(1)
        self._edit("Version two", "Renamed.")
        self.codebook.tag_version(2)
        self.client.login(username=self.data["expert"].username, password="123")

        response = self.client.get(
            reverse("codebook-diff", args=(self.codebook.pk,)), {"batch_old": 1, "batch_new": 2}
        )

        assert [c.rationale for c in response.context["changes"]] == ["Renamed."]
        assert "Renamed." in response.content.decode()
