#!/bin/sh
# Runs pending Alembic migrations before starting the given command, so a
# fresh `docker compose up` always has an up-to-date schema instead of
# relying on someone manually running `alembic upgrade head`.
set -e

echo "Applying database migrations..."
alembic upgrade head

exec "$@"
