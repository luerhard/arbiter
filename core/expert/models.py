from django.db import models


class CodebookDraft(models.Model):
    """An expert's uncommitted codebook edit for one assignment.

    The draft lives server-side from the moment the expert clicks Save in
    the codebook editor, so a reload, crash, or expired session never loses
    an edit. Committing the decision turns the draft into a git commit and
    deletes it; Undo deletes it directly.
    """

    assignment = models.OneToOneField(
        "data.ExampleAssignment",
        related_name="codebook_draft",
        on_delete=models.CASCADE,
    )
    content = models.TextField()
    rationale = models.TextField(blank=True)
    # Codebook HEAD commit the draft was based on; used as an optimistic
    # lock when committing.
    base_revision = models.CharField(max_length=40)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"CodebookDraft for assignment {self.assignment_id}"
