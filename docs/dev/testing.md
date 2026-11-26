# Tests and documentation

## Run the tests

The tests use [pytest](https://docs.pytest.org/) with [pytest-django](https://pytest-django.readthedocs.io/) and live in `core/tests/`, one folder per app. They need the database and Redis of the development setup. With it running:

```bash
docker compose exec web python -m pytest -q
```

Add a path to run some of them, for example `tests/projects/`, or `-k` with part of a test's name.

The test database is created on the first run and kept for the next ones (`--reuse-db`). After a change to the models, add `--create-db` once.

### Outside the container

To run the tests from your editor, for example in VS Code's test view, install the Python environment on your computer:

```bash
uv sync
```

The tests then reach the database and Redis of the running containers through their ports. They read the database settings from the environment, so add one line to `.env`, which the containers ignore:

```bash
POSTGRES_HOST=localhost
```

and load `.env` into your shell before running the tests from `core/`:

```bash
set -a; . ./.env; set +a
cd core
uv run pytest -q
```

With [direnv](https://direnv.net/), the repository's `.envrc` loads `.env` by itself whenever you enter the folder.

## Continuous integration

GitHub Actions runs three workflows (`.github/workflows/`):

| Workflow        | When                               | What it does                                               |
| --------------- | ---------------------------------- | ---------------------------------------------------------- |
| `tests.yml`     | pushes and pull requests to `main` | runs the whole test suite in the development setup         |
| `formatter.yml` | every push                         | runs ruff and Prettier and commits their fixes             |
| `docs.yml`      | pushes to `main`                   | builds this documentation and publishes it on GitHub Pages |

## The documentation

The documentation is built with [Sphinx](https://www.sphinx-doc.org/) from Markdown files ([MyST](https://myst-parser.readthedocs.io/)) in `docs/`:

| Folder           | What it holds                                                        |
| ---------------- | -------------------------------------------------------------------- |
| `index.md`       | the start page, and the navigation (the `toctree` blocks at its end) |
| `get-started/`   | for everyone: how Arbiter works, signing in                          |
| `annotators/`    | for annotators                                                       |
| `project-leads/` | for project leads and experts                                        |
| `admin/`         | for whoever runs the server                                          |
| `dev/`, `api/`   | for developers; `api/` documents the code from its docstrings        |
| `screenshots/`   | the pictures, and the script that takes them                         |
| `_static/`       | the style of the documentation (`custom.css`), its fonts and logo    |

When you change what Arbiter does, change the page that describes it in the same pull request.

### Build it

```bash
cd docs
uv run sphinx-build -b html . _build/html
```

Then open `docs/_build/html/index.html`. To see changes while you write, let [sphinx-autobuild](https://github.com/sphinx-doc/sphinx-autobuild) rebuild the pages and reload the browser:

```bash
uv run --with sphinx-autobuild sphinx-autobuild -a docs docs/_build/html --port 8001
```

and open <http://localhost:8001>. `-a` rebuilds every page each time; without it, the navigation of pages you did not touch can stay outdated.

### Screenshots

The screenshots are taken from the demo data by a script, so that they can be renewed whenever the interface changes. It drives a browser with [Playwright](https://playwright.dev/python/) and runs on your computer, with the development setup running:

```bash
uv run --with playwright python docs/screenshots/shoot.py            # all of them
uv run --with playwright python docs/screenshots/shoot.py discuss    # those of one page
```

Before each page it rebuilds the demo data in the state the page needs (`manage.py demodata --stage …`); this replaces the demo projects in your development database. The pictures are taken in light mode at twice the resolution and saved in `docs/screenshots/`. The script uses the Chromium of your system, `/usr/bin/chromium-browser`; set `CHROMIUM` to another path, or run `uv run --with playwright playwright install chromium` once and set `CHROMIUM` to an empty value.

For a new screenshot, add a function to `shoot.py` and use the demo accounts and projects. If a picture needs a state the demo data does not have, extend `core/projects/management/commands/demodata.py`; its test is `core/tests/projects/test_demodata.py`.
