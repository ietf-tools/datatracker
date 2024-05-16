#!/bin/bash

echo "Running Datatracker checks..."
./ietf/manage.py check

echo "Running Datatracker migrations..."
./ietf/manage.py migrate --settings=settings_local

echo "Starting Datatracker..."

gunicorn \
          --workers "${DATATRACKER_GUNICORN_WORKERS:-9}" \
          --max-requests "${DATATRACKER_GUNICORN_MAX_REQUESTS:-32768}" \
          --timeout "${DATATRACKER_GUNICORN_TIMEOUT:-180}" \
          --bind :8000 \
          --log-level "${DATATRACKER_GUNICORN_LOG_LEVEL:-info}" \
          ietf.wsgi:application
