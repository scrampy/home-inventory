# Home Inventory

A phone-friendly web app for a household to track what it has, where it's kept, and what to buy. Several families can use one installation, and each family sees only its own data.

This is a rebuild. The earlier Gemini-built version is tagged `legacy-gemini`; its specs and mockups are kept in [docs/legacy](docs/legacy). The plan and progress are in [docs/REBUILD_PLAN.md](docs/REBUILD_PLAN.md).

**Built so far:**
- **Phase 1:** accounts (sign up, log in, password reset by email) and families (invite by email, accept, admin/member roles, remove members, leave, belong to several families and switch between them).
- **Phase 2:** the family's catalog: locations, stores and aisles (add, rename, delete, with one-tap common suggestions) and items (quick add by name, search, and an edit page for aisle, stores, unit, low-stock level and notes).

## Stack

Flask 3 with server-rendered Jinja pages and Bootstrap 5 · SQLAlchemy 2 with Flask-Migrate (Alembic) · SQLite · Flask-Login · Flask-WTF (CSRF) · Flask-Limiter · Mailjet for email · pytest and Playwright.

## Run it locally (Windows)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
copy .env.example .env
.venv\Scripts\flask --app wsgi db upgrade
.venv\Scripts\flask --app wsgi run --port 5050
```

Open http://localhost:5050. Without Mailjet keys, emails (invites, password resets) are printed to the console, and you can copy the link from there.

## Tests

```powershell
.venv\Scripts\python -m pytest                                  # unit and integration tests
.venv\Scripts\python -m pytest -m e2e --browser-channel msedge  # browser test, using installed Edge
```

## Changing the database schema

Edit `homeinv/models.py`, then:

```powershell
.venv\Scripts\flask --app wsgi db migrate -m "describe the change"
.venv\Scripts\flask --app wsgi db upgrade
```

Review the generated file in `migrations/versions/` before committing. `tests/test_app.py::test_migrations_match_models` fails if the models and migrations drift apart.

## Layout

```
homeinv/
  __init__.py     app factory: config, extensions, blueprints, error pages
  config.py       settings from environment variables; production refuses to start without required ones
  models.py       User, Family, Membership, Invitation; catalog: Location, Store, Aisle, Item
  security.py     reset tokens, safe redirects, email links, family access checks and
                  family-scoped lookups (every family-owned query goes through these)
  auth.py         sign up, log in, log out, password reset
  family.py       family page, invites, roles, members, switching families
  catalog.py      locations, stores, aisles (shared routes) and items
  email.py        Mailjet / console / in-memory email backends
  forms.py        WTForms forms
  templates/      Jinja templates (base, auth, family, email)
migrations/       Alembic migrations
tests/            pytest tests (helpers.py has the shared helpers); tests/e2e has the browser tests.
                  test_isolation.py tries other families' IDs on every route that takes one.
wsgi.py           entry point: gunicorn wsgi:app
```

## Production

The `Dockerfile` builds a production image. On start, it updates the database schema and serves the app with gunicorn on `$PORT`, keeping the SQLite database in `/app/data` (mount a persistent volume there). Required settings are `SECRET_KEY` (or the older name `FLASK_SECRET_KEY`), `APP_BASE_URL`, and the Mailjet keys and sender, unless `EMAIL_BACKEND=console`. The app won't start if any are missing. Step-by-step Coolify setup: [docs/DEPLOY.md](docs/DEPLOY.md).
