# Rebuild plan

Decided 2026-10-20: rebuild rather than continue the Gemini-built code (tag `legacy-gemini`). That code mixed families' data, had a live password-reset bypass, and had no migrations. The live database holds nothing worth keeping, so there's no data migration: the rebuild starts empty.

## Principles

- **Family separation built in.** Every family-owned table has a required `family_id`. Names are unique within a family, not globally. Lookups go through one helper that treats other families' records as not found. Tests try other families' IDs on every route.
- **Server-rendered pages**, Bootstrap 5, and htmx for in-place updates (+/− buttons, check-offs). No React.
- **Every schema change is a migration.** A test checks that migrations match the models.
- **CSRF on every form, rate limits** on login, signup, password reset and invites. **No debug or test routes** in the app (a test enforces this).
- **Phone-first.** Every screen must fit 375 px wide with no sideways scrolling.

## Phases

| # | Phase | Status |
|---|---|---|
| 1 | Skeleton, accounts (sign up, log in, password reset), families (invite by email, accept, roles, remove, leave, switch) | **Done** (branch `rebuild`) |
| 2 | Catalog: locations, stores, aisles, items, and an item edit page where you attach stores | **Done** (branch `rebuild`) |
| 3 | Inventory: view per location, +/− buttons, quick "create and add", totals across locations | **Done** (branch `rebuild`) |
| 4 | Redesign (Find / Places tree / List / More) and shopping list: store mode, aisle order, cart, put-away, running-low suggestions | **Done** (branch `rebuild`) |
| 5 | Deploy: Dockerfile, Coolify app pointed at the new code, persistent volume for SQLite, nightly backups | Dockerfile done, Coolify steps in [DEPLOY.md](DEPLOY.md); backups to do |

### Phase 2: what was built

- `FamilyOwned` mixin in `models.py`: required, indexed `family_id`, plus `name` and `name_key` (trimmed, lowercased) with a unique `(family_id, name_key)` constraint. Names are shown as typed, with extra spaces collapsed.
- Every family-owned lookup goes through `security.family_select` / `family_rows` / `get_for_family_or_404` / `name_in_use`. `tests/test_isolation.py` tries another family's IDs on every route that takes an ID, and fails if a new ID route isn't listed there.
- An item's aisle and stores can only be chosen from the current family's (form choices are limited to them). Deleting an aisle leaves its items with no aisle; deleting a store unlinks it from items.
- Items have `low_stock_threshold` ready for the low-stock view.

### Notes for phase 3 and 4

- Inventory rows (item × location × quantity) are family-owned too: give them `family_id`, and check that the item and location belong to the same family.
- Done in phase 3: item counts on the Locations page; deleting a location removes its stock rows (the confirmation says so); inventory is the home page.
- The old app's shopping-list flags (Get/Got in ItemStores.csv) weren't imported. The importer lists which items had them.
- The shopping list gets `family_id` and a unique `(family_id, item_id)` constraint.
- Aisles are sorted alphabetically. If the shopping list should follow walking order, add an aisle `position` with up/down controls.

### Notes from phase 4

- Design: the clickable prototype is the "Home Inventory redesign" canvas (claude.ai artifact).
- SQLite migrations run with foreign keys off (`migrations/env.py`): rebuilding a table otherwise cascade-deletes rows in other tables. `test_migrations_keep_existing_rows` guards this.
- Back up the live database with SQLite's backup API, not by copying the file: in WAL mode, a plain copy can miss recent changes.

## Deploying (phase 5)

- Coolify app `m8c8wg0sockg4kowsckcoows` deploys `main` of this repo through a GitHub webhook. Merging `rebuild` into `main` replaces the old app.
- Before that: add a persistent volume (for example `/data/home-inventory` → `/app/data`), set `DATABASE_URL=sqlite:////app/data/homeinv.db`, and set the production variables listed in `.env.example`.
- Start command: `flask --app wsgi db upgrade && gunicorn -w 2 -b 0.0.0.0:8000 wsgi:app`.
- `PROXY_HOPS`: probably 2 (Cloudflare Tunnel → Traefik). Check `X-Forwarded-For` at deploy time, because rate limits depend on getting the real client IP.
- Consider making the GitHub repo private.

## Not yet done

- **Email verification for ordinary sign-ups.** Invited users are marked verified because they clicked an emailed link. Others are not verified, and nothing currently depends on it.
- **Deleting a family.** The only member of a family can't leave it yet.
- **Rate limits are kept in memory per worker.** That's fine for one small instance. If it ever scales out, use Redis.
