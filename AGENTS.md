# Repository Guidelines

## Project Structure & Module Organization
- Root: `manage.py` and project package `jadeed/` (settings, urls, wsgi/asgi).
- Apps: create feature apps under `apps/<name>/` with `models.py`, `views.py`, `urls.py`, `tests/`.
- Templates: `templates/` with app‑scoped subfolders; Static assets in `static/`.
- Migrations: versioned in each app’s `migrations/` and committed.

## Build, Test, and Development Commands
- Create venv: `python3 -m venv .venv && source .venv/bin/activate`.
- Install deps (early stage): `pip install "Django>=4.2"` (see README). When `requirements.txt` exists: `pip install -r requirements.txt`.
- DB setup: `python manage.py migrate`.
- Run locally: `python manage.py runserver`.
- Run tests: `python manage.py test` (optionally with coverage: `coverage run manage.py test && coverage html`).

## Coding Style & Naming Conventions
- Python: 4‑space indents, PEP 8. Prefer `black` and `isort` if configured; otherwise keep lines ≤ 88 chars.
- Django apps: `apps/<app_name>/` in snake_case; models CamelCase; functions snake_case; settings UPPER_CASE.
- URLs: namespace per app; reverse with `app_namespace:view_name`.
- Avoid fat views; prefer services/forms/serializers as modules under the app.

## Testing Guidelines
- Place tests in `apps/<app>/tests/` mirroring module names (e.g., `test_models.py`, `test_views.py`).
- Use Django TestCase and RequestFactory; mock external services.
- Aim for coverage on critical paths (models, services, permissions). Add regression tests for bugs.

## Commit & Pull Request Guidelines
- Commits: imperative mood, small scope, include rationale (e.g., `feat(apps.tasks): add async worker`).
- Branches: `type/short-topic` (e.g., `fix/login-redirect`).
- PRs: clear description, linked issues, reproduction/verification steps, screenshots for UI, notes on migrations and rollout.

## Security & Configuration Tips
- Do not commit secrets; use `.env` and `os.environ` in settings. Rotate `SECRET_KEY` per env.
- Keep `DEBUG=False` in production; validate `ALLOWED_HOSTS`.
- Review migrations in PRs; ensure no destructive ops without backups.

## Agent-Specific Instructions
- Follow this file’s scope for the entire repo. Keep changes minimal, focused, and aligned with existing patterns. Update README and tests when behavior changes.
