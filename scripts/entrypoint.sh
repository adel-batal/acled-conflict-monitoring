#!/bin/sh
set -e

# Run migrations before starting the server
alembic upgrade head

exec "$@"
