from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from . import room_state
from .models import Room
from projects.models import Batch


@receiver(post_delete, sender=Batch)
def delete_chat(sender, instance, **kwargs):  # noqa: ARG001
    """A chat room shares the id of its batch but has no foreign key to it, so it is not
    deleted along with the batch. Runs for every way a batch goes: its own deletion, its
    project's, the admin.
    """
    batch_id = instance.pk  # Django sets instance.pk to None once the deletion is done
    Room.objects.filter(pk=batch_id).delete()
    transaction.on_commit(lambda: room_state.delete_state(batch_id))
