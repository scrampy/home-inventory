# Deploying on Coolify

**Status (2026-10-20):** deployed from branch `rebuild` at https://home-inventory-dev.scrampy.cc. The settings below are in place. To redeploy after pushing, use the API (below) or the Redeploy button. The GitHub webhook can't reach Coolify, so pushes don't deploy on their own.

## Deploying through the API

The `claude-code` API token (deploy, read, write) is stored as `COOLIFY_API_TOKEN` in `bookshelf-analyzer/.env`.

```bash
curl -H "Authorization: Bearer $COOLIFY_API_TOKEN" "http://10.2.2.240:8000/api/v1/deploy?uuid=m8c8wg0sockg4kowsckcoows"
```

The app runs from the `Dockerfile`. On start, the container updates the database schema and then serves the app with gunicorn on `$PORT`. It keeps its SQLite database in `/app/data`, which must be a persistent volume.

## Settings for the existing Coolify app (`home-inventory`, `m8c8wg0sockg4kowsckcoows`)

Coolify dashboard: http://10.2.2.240:8000 (home network only).

1. **Configuration → General**
   - **Build Pack:** `Dockerfile` (was Nixpacks).
   - **Ports Exposes:** leave it at `3000`. Coolify sets `PORT=3000`, and the container listens on it.
2. **Configuration → Source:** **Branch** `rebuild` (switch back to `main` once `rebuild` is merged).
3. **Environment Variables:** add
   - `APP_BASE_URL` = `https://home-inventory-dev.scrampy.cc` (used for links in emails)
   - `PROXY_HOPS` = `2` (Cloudflare Tunnel → Traefik; used to rate-limit by the visitor's real IP)
   - `PORT` = `3000`
   - `SECRET_KEY` = 64 random characters, runtime only (set on 2026-10-20; the old `FLASK_SECRET_KEY` is 31 characters, too short)

   Keep `FLASK_SECRET_KEY` and the four `MAILJET_*` variables: the app reads them under their old names. `FLASK_SECRET_KEY` must be at least 32 characters; if it's shorter, the container stops with a clear error, so replace it:
   ```
   py -c "import secrets; print(secrets.token_urlsafe(48))"
   ```
   If the Mailjet keys no longer work, also add `EMAIL_BACKEND` = `console`. Emails then go to the container log instead of being sent. Invites still work, because the family page shows a copyable invite link. Password resets don't, until Mailjet works again.

   `FLASK_ENV` and `SECURITY_PASSWORD_SALT` are no longer used and can be deleted.
4. **Persistent Storage → Add → Volume:** name `home-inventory-data`, destination path `/app/data`. Without it, every redeploy starts with an empty database.
5. **Health check:** path `/healthz`, port `3000` (was `/`, which redirects to the login page).
6. **Deploy.** The deploy log should end with lines like:
   ```
   Running upgrade  -> 2190ecdb91dd, accounts and families
   Running upgrade 2190ecdb91dd -> 3c977638910f, catalog: ...
   Listening at: http://0.0.0.0:3000
   ```

## Trying it out

Open https://home-inventory-dev.scrampy.cc and create an account (this creates your family). To try family features, use a second browser or a private window for the second person:

- **Invite:** family page → Invite someone. The page shows the invite link right away. Open it in the other browser and create an account with the invited email address.
- **Roles:** Make admin / Make member. A family always keeps at least one admin.
- **Remove:** Remove a member. That person is then asked to create a family of their own.
- **Separation:** sign up a third person with their own family. They see none of your items, stores or members, and your item URLs show "Not found" for them.

## If something goes wrong

- **Container stops right after starting:** look for `Missing production settings: ...` in the log. It names the setting that's missing.
- **`/app/data is not writable`:** the persistent storage in step 4 is missing or mounted somewhere else.
- **Coolify dashboard shows HTTP 500:** see the "Coolify dashboard 500" incident in `bookshelf-analyzer/PROJECT_NOTES.md`. Coolify's cache files were left empty by an unclean VM restart.
