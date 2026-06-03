import logging
import shutil

from django.db import models
from django.urls import reverse
from git import GitCommandError
from git import Repo

from core import settings

# Create your models here.

log = logging.getLogger(__name__)


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

    def diff(self, old: int, new: int):
        tag_old = f"batch_{old}"
        tag_new = f"batch_{new}"
        diff = self.repo.git.diff(
            "--unified=99999",
            "--word-diff",
            tag_old,
            tag_new,
            "--",
            self.file.name,
        )
        # if files differ
        if len(diff) > 0:
            diff_lines = diff.splitlines()
            diff = "\n".join(diff_lines[5:])
            return diff
        # else files are equal
        content = self.repo.git.show(f"{tag_old}:{self.file.name}")
        return content

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

    def get_as_context(self, batch_number: int):
        return {"codebook": self, "content_diff": self.diff(batch_number - 1, batch_number)}
