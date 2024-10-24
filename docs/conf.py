# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import os
from pathlib import Path
import sys

import django

project = "AnnotationTool"
copyright = "2024, Lukas Erhard, Susanne Hindennach"
author = "Lukas Erhard, Susanne Hindennach"
release = "0.0.1"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinxcontrib_django",
]

myst_enable_extensions = [
    "colon_fence",
]

autodoc_member_order = "bysource"

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "**.ipynb_checkpoints"]

# Django specific configuration


sys.path.append(str(Path(__file__).parent.parent / "core"))
os.environ["DJANGO_SETTINGS_MODULE"] = "core.settings"
django.setup()

django_settings = "core.settings"
# Include the database table names of Django models
django_show_db_tables = True  # Boolean, default: False
# Add abstract database tables names (only takes effect if django_show_db_tables is True)
django_show_db_tables_abstract = True  # Boolean, default: False

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
