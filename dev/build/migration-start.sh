#!/bin/bash

echo "Running Datatracker checks..."
./ietf/manage.py check

echo "Running Datatracker migrations..."
./ietf/manage.py migrate --skip-checks --settings=settings_local

echo "Done!"
