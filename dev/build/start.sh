#!/bin/bash

echo "Running Datatracker checks..."
./ietf/manage.py check

echo "Running Datatracker migrations..."
./ietf/manage.py migrate --settings=settings_local

echo "Starting Datatracker..."
./ietf/manage.py runserver 0.0.0.0:8000 --settings=settings_local
