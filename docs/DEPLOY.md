# Deploying

## brain-server (Docker Compose), replacing Coolify

**Status (2026-11-09):** live. https://home-inventory-dev.scrampy.cc is served from brain-server (192.168.0.157) since the evening of 2026-11-09, at commit d09b816. The Coolify app is stopped but not deleted; its volume still holds the old database and backups. We moved because the Coolify VM runs on a Windows PC ("geforce") that restarts without warning, and the VM's address can change when it comes back.

In Cloudflare, the hostname is a route of the **docker-host** tunnel (brain-server's own, configured by file, so the dashboard can't edit it). The old **virtualbox-host** tunnel on geforce no longer has this hostname; it still serves bookshelf-analyzer.

How a request will reach the app: Cloudflare → brain-server's own cloudflared tunnel (systemd service, routes in `/etc/cloudflared/config.yml`) → `127.0.0.1:3001` → the `home-inventory` container. That is one proxy, so `PROXY_HOPS=1`.

Files on brain-server, in `~/compose/home-inventory` (the same layout as the other apps in `~/compose`):

| | |
|---|---|
| `compose.yaml` | copy of [deploy/brain-server/compose.yaml](../deploy/brain-server/compose.yaml) |
| `.env` | secrets and settings, chmod 600, never committed. Keys: `SECRET_KEY`, `APP_BASE_URL`, `MAILJET_API_KEY`, `MAILJET_SECRET_KEY`, `MAILJET_SENDER_EMAIL`, `MAILJET_SENDER_NAME`, `ALEXA_SKILL_ID`, `ALEXA_INVOCATION_NAME` |
| `src/` | git checkout of this repo, built with its Dockerfile |
| `data/` | `homeinv.db`, and `backups/` made by the deploy script |

The app listens on `127.0.0.1` only, so nothing on the network can reach it except through the tunnel. To look at it from this PC:

```bash
ssh -N -L 3001:127.0.0.1:3001 brain@192.168.0.157
```

then open http://localhost:3001.

### Deploying

Push first: brain-server builds from GitHub. Then, from the repo:

```bash
deploy/brain-server/deploy.sh
```

It backs up the database to `data/backups/`, checks out the latest `rebuild` commit, builds, starts it and waits for `/healthz`. Other commands: `deploy.sh <branch|sha>`, `deploy.sh status`, `deploy.sh backup [label]`, `deploy.sh rollback <tag>`. A rollback doesn't undo a schema migration; if the newer version migrated the database, stop the app and put the backup the deploy made back as `data/homeinv.db`.

### Copying a database in

Always use SQLite's backup API (`.backup()`), never a plain file copy, because the database runs in WAL mode. A file you copy in belongs to your user; the entrypoint hands it to the app user at start-up. Before 2026-11-09 it didn't, and the app could read the database but not write it.

### Cutover checklist (Coolify → brain-server)

Done on 2026-11-09. Kept as the recipe for the other apps on the VM. Copy the database before switching DNS: once DNS points at brain-server, visitors write to that copy.

1. Stop the Coolify app so nobody writes to the old database: `GET /api/v1/applications/m8c8wg0sockg4kowsckcoows/stop`.
2. On brain-server, `docker compose stop`. Copy a fresh `.backup()` of the live database into `data/homeinv.db`, then `docker compose up -d`.
3. Add this route to `/etc/cloudflared/config.yml`, above the final `http_status:404` line, then `sudo systemctl restart cloudflared`. Plex, Home Assistant and photos drop for a few seconds.
   ```yaml
     - hostname: home-inventory-dev.scrampy.cc
       service: http://localhost:3001
   ```
4. In the Cloudflare dashboard, point the DNS record `home-inventory-dev` (CNAME, proxied) at `31ec14f0-2cdd-431c-a3c4-fb9b08003c08.cfargotunnel.com`. If the geforce tunnel lists this hostname under its public hostnames, remove it there first.
5. Check: https://home-inventory-dev.scrampy.cc/healthz, log in, an Alexa command, both tablets.
6. To go back: point the DNS record back at the geforce tunnel and start the Coolify app again (copy the database back first if anything was saved on brain-server).

## Coolify (retired 2026-11-09)

The app was stopped on 2026-11-09 after the move to brain-server. To fall back to it, copy brain-server's database back into its volume first, start it with `GET /api/v1/applications/m8c8wg0sockg4kowsckcoows/start`, and add the route `home-inventory-dev.scrampy.cc` → `http://10.2.2.240:3001` back to the virtualbox-host tunnel. The rest of this section describes how it was set up.

**Status (2026-10-20):** deployed from branch `rebuild`. The settings below were in place. To redeploy after pushing, use the API (below) or the Redeploy button. The GitHub webhook can't reach Coolify, so pushes don't deploy on their own.

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
