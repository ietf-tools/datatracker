#!/bin/bash

echo "Fixing permissions..."
chmod -R 777 ./
echo "Ensure all requirements.txt packages are installed..."
pip --disable-pip-version-check --no-cache-dir install -r requirements.txt
echo "Installing node packages..."
npm install
echo "Building static assets..."
npm run build
npm run legacy:build
echo "Creating data directories..."
chmod +x ./docker/scripts/app-create-dirs.sh
./docker/scripts/app-create-dirs.sh

./ietf/manage.py check
./ietf/manage.py migrate --fake-initial

