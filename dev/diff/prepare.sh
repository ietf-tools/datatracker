#!/bin/bash

echo "Fixing permissions..."
chmod -R 777 ./
echo "Copying config files..."
cp ./dev/diff/settings_local.py ./ietf/settings_local.py
echo "Ensure all requirements.txt packages are installed..."
pip --disable-pip-version-check --no-cache-dir install -r requirements.txt
echo "Compiling native node packages..."
yarn rebuild
echo "Building static assets..."
yarn build
yarn legacy:build
echo "Creating data directories..."
chmod +x ./docker/scripts/app-create-dirs.sh
./docker/scripts/app-create-dirs.sh
