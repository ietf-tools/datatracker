#!/bin/bash

echo "Running Datatracker migrations..."
./ietf/manage.py migrate --settings=settings_local

echo "Done!"
