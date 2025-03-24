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
    def content(self):
        full_path = settings.CODEBOOKS_ROOT / self.git_dir
        codebook_file = full_path / "main.md"
        return codebook_file.read_text()

    def get_absolute_url(self):
        return reverse("codebook-view", kwargs={"pk": self.pk})

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
        else:
            # modify codebook
            full_path = settings.CODEBOOKS_ROOT / self.git_dir
            codebook_file = full_path / "main.md"

            # do nothing if no content was set.
            if not content:
                log.debug("No content was given.")
                super().save(**kwargs)
                return

            if not content.endswith("\n"):
                content += "\n"
            codebook_file.write_text(content)

            repo = Repo(full_path)
            repo.git.add(".")
            if not commit_message:
                commit_message = "updated"
            try:
                repo.git.commit(m=commit_message)
            except GitCommandError as e:
                if "nothing to commit, working tree clean" in str(e):
                    pass
                else:
                    raise e

        super().save(**kwargs)
