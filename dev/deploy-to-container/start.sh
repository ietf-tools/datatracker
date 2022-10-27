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
echo "Running Datatracker migrations..."
./ietf/manage.py migrate
echo "Starting Datatracker..."
./ietf/manage.py runserver 0.0.0.0:8000 --settings=settings_local
