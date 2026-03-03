"""Select default settings when DJANGO_SETTINGS_MODULE points to ``core.settings``."""

import os

_selected_settings = os.getenv("DJANGO_SETTINGS_MODULE", "core.settings")
if _selected_settings.endswith(".prod"):
    from .prod import *  # noqa: F403
else:
    from .dev import *  # noqa: F403
