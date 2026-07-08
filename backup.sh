#!/usr/bin/env bash
# Create a full backup (database dump + media incl. codebooks) from the host.
# Run this before touching the containers, e.g. before a rebuild, migration or update.
#
# Usage: ./backup.sh [compose-file]
#   compose-file defaults to docker-compose.prod.yml
#
# The archive ends up in ./backups/ on the host (bind-mounted into the container).

set -euo pipefail

cd "$(dirname "$0")"

COMPOSE_FILE="${1:-docker-compose.prod.yml}"
compose() { docker compose -f "$COMPOSE_FILE" "$@"; }

mkdir -p backups

if compose exec -T web true 2>/dev/null; then
    # Web container is running: back up in place.
    compose exec -T web python manage.py backup
else
    # Stack is down: spin up a one-off web container (starts db as dependency).
    echo "web container not running, using a one-off container..."
    compose run --rm -T web python manage.py backup
fi

latest="$(ls -t backups/backup_*.zip 2>/dev/null | head -n 1 || true)"
if [ -n "$latest" ]; then
    echo "Host copy: $latest ($(du -h --apparent-size "$latest" | cut -f1))"
fi
