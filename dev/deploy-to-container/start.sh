#!/bin/bash

echo "Fixing permissions..."
chmod -R 777 ./
echo "Ensure all requirements.txt packages are installed..."
pip --disable-pip-version-check --no-cache-dir install -r requirements.txt
echo "Creating data directories..."
chmod +x ./app-create-dirs.sh
./app-create-dirs.sh
echo "Running Datatracker checks..."
./ietf/manage.py check

# Migrate, adjusting to what the current state of the underlying database might be:

echo "Running Datatracker migrations..."
/usr/local/bin/python ./ietf/manage.py migrate --settings=settings_local

echo "Starting Datatracker..."
./ietf/manage.py runserver 0.0.0.0:8000 --settings=settings_local
