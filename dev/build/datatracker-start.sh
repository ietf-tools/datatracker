#!/bin/bash

echo "Running Datatracker checks..."
./ietf/manage.py check

echo "Running Datatracker migrations..."
./ietf/manage.py migrate --settings=settings_local

echo "Running collectstatic..."
./ietf/manage.py collectstatic

echo "Starting Datatracker..."

gunicorn \
          --workers 9 \
          --max-requests 32768 \
          --timeout 180 \
          --bind :8000 \
          --log-level info \
          ietf.wsgi:application
          
          # Leaving this here as a reminder to set up the env in the chart
          # Remove this once that's complete.
          #--env SCOUT_NAME=Datatracker \
