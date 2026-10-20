#!/bin/sh
# Container start: make sure the data folder is writable, update the database
# schema, then serve the app.
set -e

if [ "$(id -u)" = "0" ]; then
    # A freshly mounted volume or host folder may belong to root. Hand it to the
    # app user, then rerun this script as that user.
    chown app:app /app/data /app/instance
    HOME=/home/app exec setpriv --reuid=app --regid=app --init-groups "$0" "$@"
fi

if ! touch /app/data/.write-test 2>/dev/null; then
    echo "ERROR: /app/data is not writable. Mount a persistent volume at /app/data." >&2
    exit 1
fi
rm -f /app/data/.write-test

flask --app wsgi db upgrade

exec gunicorn wsgi:app \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-2}" \
    --access-logfile - \
    --error-logfile -
