from dataclasses import dataclass
from datetime import datetime
import json
import logging
import shutil

from django.apps import apps
from django.db import models
from django.urls import reverse
from git import GitCommandError
from git import Repo

from core import settings

log = logging.getLogger(__name__)


@dataclass
class CodebookChange:
    """One saved change of the codebook text (a commit that changed main.md)."""

    sha: str
    date: datetime
    rationale: str
    decision_text: str  # the sample an expert decided when saving the change, if any
    when: str  # "before batch 1", "during batch 2"


def _commit_info(message: str) -> dict:
    # changes are committed with a JSON message (rationale, decision metadata); old or
    # generated commits have plain text
    try:
        info = json.loads(message)
    except ValueError:
        return {}
    return info if isinstance(info, dict) else {}


class Codebook(models.Model):
    project = models.ForeignKey(
        "projects.Project",
        related_name="codebook",
        on_delete=models.CASCADE,
    )

    git_dir = models.FilePathField(
        path=settings.CODEBOOKS_ROOT,
        allow_files=False,
        allow_folders=True,
    )

    @property
    def file(self):
        full_path = settings.CODEBOOKS_ROOT / self.git_dir
        codebook_file = full_path / "main.md"
        return codebook_file

    @property
    def content(self):
        return self.file.read_text()

    @property
    def repo(self):
        full_path = settings.CODEBOOKS_ROOT / self.git_dir
        return Repo(full_path)

    def get_absolute_url(self):
        return reverse("codebook-view", kwargs={"codebook_id": self.pk})

    def tag_version(self, batch_number: int):
        tag = f"batch_{batch_number}"
        if tag in self.repo.tags:
            self.repo.delete_tag(tag)
        self.repo.create_tag(tag)

    def untag_version(self, batch_number: int):
        tag = f"batch_{batch_number}"
        if tag in self.repo.tags:
            self.repo.delete_tag(tag)

    def tagged_batches(self) -> set[int]:
        """The batch numbers with a codebook version: batch_N is tagged when batch N starts
        annotation, batch_0 is the empty codebook. Deleting a batch removes its tag."""
        return {
            int(number)
            for tag in self.repo.tags
            if (number := tag.name.removeprefix("batch_")).isdigit()
        }

    def _word_diff(self, old_ref: str, new_ref: str) -> str:
        """The new text with {+added+} and [-removed-] words, "" if nothing changed."""
        diff = self.repo.git.diff(
            "--unified=99999",
            "--word-diff",
            old_ref,
            new_ref,
            "--",
            self.file.name,
        )
        return "\n".join(diff.splitlines()[5:])  # without the diff header

    def diff(self, old: int, new: int | None = None) -> str:
        """What changed between the versions batch old and batch new started with; without
        new, up to the current text."""
        return self._word_diff(f"batch_{old}", f"batch_{new}" if new is not None else "HEAD")

    def _is_empty(self, batch: int) -> bool:
        return not self.repo.git.show(f"batch_{batch}:{self.file.name}").strip()

    def changes(self) -> list[CodebookChange]:
        """Every change of the codebook text, newest first."""
        root = self.repo.git.rev_list("--max-parents=0", "HEAD").split()
        log_text = self.repo.git.log("--format=%H%x1f%aI%x1f%B%x1e", "--", self.file.name)
        # the first batch whose version contains a change
        batches = sorted(self.tagged_batches() - {0})
        contained = {
            number: set(self.repo.git.rev_list(f"batch_{number}", "--", self.file.name).split())
            for number in batches
        }
        changes = []
        for entry in log_text.split("\x1e"):
            if not entry.strip():
                continue
            sha, date, message = entry.strip().split("\x1f", 2)
            if sha in root:
                continue  # the empty codebook every project starts with
            info = _commit_info(message)
            first = next((n for n in batches if sha in contained[n]), None)
            before = [n for n in batches if first is None or n < first]
            if first is None:
                when = f"during batch {before[-1]}" if before else "before the first batch"
            elif before:
                when = f"during batch {before[-1]}"
            else:
                when = f"before batch {first}"
            changes.append(
                CodebookChange(
                    sha=sha,
                    date=datetime.fromisoformat(date),
                    rationale=str(info.get("rationale", "")).strip(),
                    decision_text=str(info.get("text", "")),
                    when=when,
                ),
            )
        return changes

    def changes_between(self, old: int, new: int | None = None) -> list[CodebookChange]:
        """The changes made after batch old started and before batch new started; without
        new, up to now."""
        new_ref = f"batch_{new}" if new is not None else "HEAD"
        shas = set(self.repo.git.rev_list(f"batch_{old}..{new_ref}").split())
        return [change for change in self.changes() if change.sha in shas]

    def last_batch_of(self, user, before: int | None = None) -> int | None:
        """The newest batch (before batch before) user annotated in that has a codebook
        version: changes since it are new to them. For an expert who annotates in no batch,
        the newest batch that started."""
        tagged = self.tagged_batches() - {0}
        if before is not None:
            tagged = {n for n in tagged if n < before}
        BatchUser = apps.get_model("projects", "BatchUser")
        own = set(
            BatchUser.objects.filter(
                user=user,
                role="A",
                batch__project_id=self.project_id,
            ).values_list("batch__batch_number", flat=True),
        )
        candidates = tagged & own if own or before is not None else tagged
        return max(candidates, default=None)

    def change(self, sha: str) -> tuple[CodebookChange, str] | None:
        """One change and what it changed, None if sha is not a change of the text."""
        change = next((c for c in self.changes() if c.sha == sha), None)
        if change is None:
            return None
        return change, self._word_diff(f"{sha}^", sha)

    def save(self, content: str | None = None, commit_message: str | None = None, **kwargs):
        if self._state.adding is True:
            # only do this on new creation
            folder = str(self.project.pk)
            self.git_dir = folder

            full_path = settings.CODEBOOKS_ROOT / folder
            # create folder
            if full_path.is_dir():
                shutil.rmtree(full_path, ignore_errors=True)

            # init git repo
            repo = Repo.init(path=full_path, mkdir=True, bare=False)
            repo.config_writer().set_value("core", "autocrlf", "input").release()
            (full_path / "main.md").write_text("\n")
            repo.git.add("main.md")
            repo.git.commit(m="initial")
            self.repo.create_tag("batch_0")
        else:
            # modify codebook

            # do nothing if no content was set.
            if not content:
                log.debug("No content was given.")
                super().save(**kwargs)
                return

            if not content.endswith("\n"):
                content += "\n"
            self.file.write_text(content)

            self.repo.git.add(".")
            if not commit_message:
                commit_message = "updated"
            try:
                self.repo.git.commit(m=commit_message)
            except GitCommandError as e:
                if "nothing to commit, working tree clean" in str(e):
                    pass
                else:
                    raise e

        super().save(**kwargs)

    def commit_decision_revision(self, commit_message: str):
        """Record a decision correction that does not change the codebook.

        The decision log in the git history is append-only: the original
        commit keeps its metadata, and the correction is appended as an
        empty commit whose message carries the revised metadata.
        """
        self.repo.git.commit("--allow-empty", m=commit_message)

    def get_as_context(self, since: int | None):
        """The codebook for a work screen, with what changed since the version batch since
        started with, up to the current text. Nothing to show without an earlier version
        (since is None) or for the first version: everything would be new."""
        context = {
            "codebook": self,
            "content_diff": "",
            "codebook_changes": [],
            "codebook_since": since,
        }
        if since is None or since not in self.tagged_batches() or self._is_empty(since):
            return context
        context["content_diff"] = self.diff(since)
        if context["content_diff"]:
            context["codebook_changes"] = self.changes_between(since)
        return context
