# Contributing to Arbiter

Thank you for your interest in contributing to Arbiter! Bug reports, feature ideas, UX/UI improvements, documentation updates, and code contributions are all very welcome.

---

## Ways to Contribute

- **Report a bug or suggest a feature**: Open an issue on our [GitHub Issue Tracker](https://github.com/luerhard/arbiter/issues). Before opening a new issue, please search existing issues to make sure it has not already been reported.
- **Improve the documentation**: Help refine the user guide (`docs/usage/index.md`) or the developer guide (`docs/dev/index.md`).

# Contributing to Arbiter

Thank you for your interest in contributing! We welcome bug reports, feature requests,
documentation improvements and code contributions.

## 1. Reporting issues

Use [GitHub issues](https://github.com/luerhard/arbiter/issues) to report bugs or suggest
features.

When reporting a bug, include:

- Steps to reproduce
- Expected behavior
- Actual behavior
- Environment details: how you run Arbiter and your role in the app (annotator, expert or administrator) and the
  phase involved (annotation, discussion, expert decision)
- Error messages or log output (`docker compose logs web`), and a screenshot for display problems

Never post real, sensitive annotation data in a public issue.

## 2. Development setup

Arbiter is developed with Docker Compose. Follow the
[installation instructions in the README](README.md#installation-and-quick-start) and
[developer guide](docs/dev/index.md)

## 3. Testing

Every code contribution should include tests to help maintain quality and reliability. We use pytest and pytest-django; the tests live in `core/tests/`, with one folder per Django app. Run
the full suite inside the development stack:

```bash
docker compose run --rm web uv run pytest -v
```

The tests also run automatically with GitHub Actions on every push and pull request to `main`.
See the [developer guide](docs/dev/index.md#run-tests) for more information on how to run tests.

## 4. Documenting changes

If your contribution changes the behavior of Arbiter or adds features, please make sure the
changes are reflected in the documentation:

- User guide: `docs/usage/index.md` (screenshots in `docs/usage/screenshots/`)
- Developer guide: `docs/dev/index.md`
- API reference: `docs/api/`.

Build the documentation locally with:

```bash
docker compose run --rm web sh -c "cd ../docs; make html"
```

## 5. Submitting a pull request

1. Fork the repository and clone your fork.
2. Create a branch from `main`.
3. Push your branch to your fork.
4. Open a pull request against `main`.
5. Clearly describe what your pull request does and reference any related issues.
6. A maintainer will review your pull request and may request changes.
