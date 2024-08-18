from django.contrib.auth.management import create_permissions
from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission

GROUPS = {
    "Admin": {
        # django specific roles
        ("logentry", ("view", "add", "change", "delete")),
        ("permission", ("view", "add", "change", "delete")),
        ("group", ("view", "add", "change", "delete")),
        ("contenttype", ("view", "add", "change", "delete")),
        ("session", ("view", "add", "change", "delete")),
        ("user", ("view", "add", "change", "delete")),
    },
    "Expert": {
        ("project", ("view", "add", "change", "delete")),
        ("projectuser", ("view", "add", "change", "delete")),
        ("batch", ("view", "add", "change", "delete")),
        ("sentence", ("view", "add", "change", "delete")),
        ("label", ("view", "add", "change", "delete")),
        ("userannotation", ("view",)),
    },
    "Annotator": {
        ("project", ("view",)),
        ("projectuser", ("view",)),
        ("batch", ("view",)),
        ("sentence", ("view",)),
        ("label", ("view",)),
        ("userannotation", ("view", "add", "change", "delete")),
    },
}


def create_groups(apps, schema_editor):  # noqa: ARG001
    # Permissions have to be created before applying them
    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, verbosity=0)
        app_config.models_module = None

    for group_name, permissions in GROUPS.items():
        group, created_at = Group.objects.get_or_create(name=group_name)
        for permisson, modes in permissions:
            for mode in modes:
                codename = f"{mode}_{permisson}"
                try:
                    permission = Permission.objects.get(codename=codename)
                    group.permissions.add(permission)
                except:
                    raise
