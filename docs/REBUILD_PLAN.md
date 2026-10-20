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
| 2 | Catalog: locations, stores, aisles, items, and an item edit page where you attach stores | To do |
| 3 | Inventory: view per location, +/− buttons, quick "create and add", totals across locations | To do |
| 4 | Shopping list: add items, check off (struck through, still visible), filter by store, sort by aisle, clear purchased, low-stock view | To do |
| 5 | Deploy: Dockerfile, Coolify app pointed at the new code, persistent volume for SQLite, nightly backups | To do |

### Phase 2 design notes

- Add a `FamilyOwned` mixin (`family_id` FK, indexed, NOT NULL) and a `get_for_family_or_404(Model, id)` helper in `security.py`. Use them for every catalog model.
- Unique constraints: `(family_id, name_key)`, where `name_key` is the trimmed, lowercased name. Show names as entered.
- Aisles stay per family for now, matching the old app. Aisles per store can come later.
- Items get `low_stock_threshold` (nullable) for phase 4's low-stock view.
- The shopping list gets `family_id`, with a unique `(family_id, item_id)` constraint.

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
