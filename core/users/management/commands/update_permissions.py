from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from ...group_permissions import GROUPS


class Command(BaseCommand):
    help = "Updates permissons for user groups"

    def handle(self, *args, **kwargs):  # noqa: ARG002

        for group_name, permissions in GROUPS.items():
            group, created_at = Group.objects.get_or_create(name=group_name)
            for permisson, modes in permissions:
                for mode in modes:
                    codename = f"{mode}_{permisson}"
                    # print(f"Granting {group} permisson: {codename}")
                    try:
                        permission = Permission.objects.get(codename=codename)
                    except permission.DoesNotExist as e:
                        msg = f"Permission does not exist {codename}"
                        raise CommandError(msg) from e

                    group.permissions.add(permission)
        self.stdout.write(self.style.SUCCESS("Updated all permissions."))
