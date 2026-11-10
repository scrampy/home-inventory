#!/usr/bin/env bash
# Deploy home-inventory to brain-server (Docker Compose in ~/compose/home-inventory).
# Run from any machine that can `ssh brain@192.168.0.157`.
#
#   deploy.sh                 deploy the latest commit of branch "rebuild"
#   deploy.sh <branch|sha>    deploy that branch or commit (must be pushed to GitHub)
#   deploy.sh status          show the running version and health
#   deploy.sh backup [label]  back up the database now
#   deploy.sh rollback <tag>  start an earlier image (tags: deploy.sh status)
#
# Every deploy backs up the database first, to data/backups/ on brain-server.
# A rollback doesn't undo database migrations: if the newer version changed the
# schema, restore the backup it made (see docs/DEPLOY.md).
set -euo pipefail

HOST="${HOMEINV_HOST:-brain@192.168.0.157}"
cmd="${1:-rebuild}"
arg="${2:-}"

ssh -o BatchMode=yes "$HOST" bash -s -- "$cmd" "$arg" <<'REMOTE'
set -euo pipefail
# ssh joins its arguments into one string, so an empty second argument disappears.
cmd="${1:-}"; arg="${2:-}"
cd ~/compose/home-inventory

backup() {
    local name="backup-$(date +%Y-%m-%d-%H%M%S)${1:+-$1}.db"
    docker exec -u app home-inventory python -c "
import os, sqlite3
os.makedirs('/app/data/backups', exist_ok=True)
src = sqlite3.connect('/app/data/homeinv.db')
dst = sqlite3.connect('/app/data/backups/$name')
src.backup(dst)
assert dst.execute('pragma integrity_check').fetchone()[0] == 'ok'
dst.close()
print('backup: data/backups/$name')
"
}

wait_healthy() {
    local s=""
    for _ in $(seq 1 30); do
        s=$(docker inspect -f '{{.State.Health.Status}}' home-inventory 2>/dev/null || echo missing)
        [ "$s" = healthy ] && { echo "health: healthy"; return 0; }
        sleep 2
    done
    echo "health: $s (not healthy after 60s). Recent log:" >&2
    docker logs --tail 30 home-inventory >&2
    return 1
}

running_tag() { docker inspect -f '{{.Config.Image}}' home-inventory 2>/dev/null | cut -d: -f2; }

case "$cmd" in
status)
    docker ps --filter name=home-inventory --format '{{.Image}}  {{.Status}}'
    echo "images on hand:"; docker images home-inventory --format '  {{.Tag}}  {{.CreatedSince}}'
    ;;
backup)
    backup "${arg}"
    ;;
rollback)
    [ -n "$arg" ] || { echo "usage: deploy.sh rollback <tag>" >&2; exit 2; }
    backup "before-rollback-to-$arg"
    IMAGE_TAG="$arg" docker compose up -d --no-build
    wait_healthy
    ;;
*)
    old=$(running_tag || true)
    [ -n "$old" ] && backup "before-deploy-from-$old"
    git -C src fetch -q origin
    if git -C src rev-parse -q --verify "origin/$cmd" >/dev/null; then
        git -C src checkout -q --detach "origin/$cmd"
    else
        git -C src checkout -q --detach "$cmd"
    fi
    new=$(git -C src rev-parse --short HEAD)
    echo "deploying $new ($(git -C src log -1 --format=%s)) over ${old:-nothing}"
    IMAGE_TAG="$new" docker compose build -q
    IMAGE_TAG="$new" docker compose up -d
    if ! wait_healthy; then
        echo "Deploy failed. To go back: deploy.sh rollback $old" >&2
        exit 1
    fi
    ;;
esac
REMOTE
