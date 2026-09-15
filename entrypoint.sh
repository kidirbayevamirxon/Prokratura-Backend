#!/bin/sh
set -e

export PYTHONPATH=/app:$PYTHONPATH

echo "Running database migrations..."
/app/.venv/bin/alembic upgrade head

echo "Ensuring initial admin exists..."
/app/.venv/bin/python backend/init_admin.py

echo "Starting server..."
exec /app/.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
