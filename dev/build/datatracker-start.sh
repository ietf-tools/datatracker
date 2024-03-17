#!/bin/bash

echo "Running Datatracker checks..."
./ietf/manage.py check

echo "Running Datatracker migrations..."
./ietf/manage.py migrate --settings=settings_local

echo "Starting Datatracker..."

gunicorn \
          --workers 53 \
          --max-requests 32768 \
          --timeout 180 \
          --bind :8000 \
          --error-logfile gunicorn_error.log \
          --log-level info \
          ietf.wsgi:application

          #--env SCOUT_NAME=Datatracker \
