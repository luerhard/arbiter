<!-- Everything marked $$PLACEHOLDER: ...$$ is information that could not be found in the repository. Fill it in or delete the line before publishing. -->

# Contributing to Arbiter

Thank you for your interest in contributing to Arbiter! Bug reports, feature ideas, UX/UI improvements, documentation updates, and code contributions are all very welcome.

$$PLACEHOLDER: ADD CODE OF CONDUCT? $$

---

## Ways to Contribute

* **Report a bug or suggest a feature**: Open an issue on our [GitHub Issue Tracker](https://github.com/luerhard/arbiter/issues). Before opening a new issue, please search existing issues to make sure it has not already been reported.
* **Improve the documentation**: Help refine the user guide (`docs/usage/index.md`) or the developer guide (`docs/dev/index.md`).
* **Fix a bug or implement a feature**: Submit a pull request addressing an open issue.

For anything larger than a small fix, please open an issue first so the planned approach can be discussed before investing time in implementation.

### Reporting a Bug
When submitting a bug report, please include:
* A clear title and description of what you did, what you expected to happen, and what actually occurred.
* Your role in the application (Annotator, Expert, or Administrator) and the phase involved (Annotation, Discussion, Expert Decision).
* Your execution environment (Docker development stack or production Compose file) along with the commit hash or release version.
* Error logs (`docker compose logs web`) and screenshots if it is a visual/UI display issue.

> ⚠️ **Important**: Never post real or sensitive annotation data in public GitHub issues.

$$PLACEHOLDER: ADD ISSUE TEMPLATE? $$

---

## Setting Up a Development Environment

Arbiter is developed using Docker Compose. The stack bundles the web application, a Vite dev server for the frontend, PostgreSQL, and Redis.

1. Follow the installation and setup steps in the [README](README.md#installation-and-quick-start).
2. Consult the [Developer Guide](docs/dev/index.md) for details on:
   * Resetting the database (`resetdb`) and loading demo data (`populatedb`).
   * Running and debugging tests (including debugging in VS Code).
   * The structure of the Django apps (`annotation`, `codebook`, `discuss`, `expert`, `notifications`, `projects`, `users`, `data`).

The Python environment is managed with [uv](https://docs.astral.sh/uv/) (requires Python 3.13 or newer; run `uv sync` to install locked dependencies). Frontend assets are managed with `npm`.

---

## Making a Change

1. **Fork** the repository and clone your fork locally.
2. **Create a branch** from `main`. Use a descriptive name following the project pattern (e.g., `87-codebook-diff-expert` or `144-fix-export-batch` matching the issue number).
3. **Implement your changes**:
   * If you modify a Django model, create and commit the migration (`docker compose exec web uv run manage.py makemigrations`).
   * If you update templates, styles, or scripts, the Vite container automatically rebuilds them in the development stack.
4. **Add or update tests** for your changes.
5. **Update documentation** if user-visible behavior or developer workflows change.
6. **Open a Pull Request against `main`**:
   * Describe what changed and why.
   * Reference the related issue (e.g., `Closes #123`).
   * Automated CI checks (GitHub Actions) will run tests and linters. Address any feedback from reviewers.

### Commit Message Guidelines
Commit messages should be concise sentences describing the change, for example:
`Refuse a codebook draft without rationale`

---

## Code Style and Quality

* **Python**: Formatted and linted with [Ruff](https://docs.astral.sh/ruff/) (line length 100, Google-style docstrings, single import per line). Rules are defined in `pyproject.toml`.
* **Templates, CSS, JS, JSON, YAML, Markdown**: Formatted with [Prettier](https://prettier.io/) (configured in `.prettierrc`).
* **Pre-commit Hooks**: Configured in `.pre-commit-config.yaml`. To enable them locally, install [pre-commit](https://pre-commit.com/) and run `pre-commit install`. Note that the Prettier hook requires frontend dependencies (`npm ci`).
* **GitHub Actions**: Runs Ruff and Prettier on every push. If formatting adjustments are needed, CI automatically commits them back to the branch (`auto-commit: fixes by ruff & prettier`). Always run `git pull` before pushing new commits.

---

## Tests

The test suite is written with `pytest` and `pytest-django` under `core/tests/` (organized by Django app). 

Run the full test suite inside the development stack:
```bash
docker compose run --rm web uv run pytest -v
```

All tests must pass prior to merging. CI executes the suite automatically on every pull request to `main`. Refer to the [Developer Guide](docs/dev/index.md#run-tests) to run specific single tests from your editor.

*(Optional)* Selenium smoke tests are located in `browser_tests/` and run on the host system. Requirements and instructions are documented in `browser_tests/conftest.py`.

---

## Documentation

* **User Guide**: `docs/usage/index.md` (screenshots stored in `docs/usage/screenshots/`)
* **Developer Guide**: `docs/dev/index.md`
* **API Reference**: `docs/api/` (generated automatically via Sphinx autodoc)

Build the documentation locally:
```bash
docker compose run --rm web sh -c "cd ../docs; make html"
```
The compiled HTML output is generated at `docs/_build/html/index.html`.

---

## Questions and Support

For questions regarding usage, architecture, or contributing to Arbiter, please open a GitHub issue.




