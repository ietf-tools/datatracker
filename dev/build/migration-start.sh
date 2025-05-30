#!/bin/bash -e

echo "Running Datatracker migrations..."
./ietf/manage.py migrate --settings=settings_local

echo "Running Blobdb migrations ..."
./ietf/manage.py migrate --settings=settings_local --database=blobdb

echo "Done!"
