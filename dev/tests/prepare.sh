#!/bin/bash

echo "Running containers:"
docker ps -a
echo "Fixing permissions..."
chmod -R 777 ./
echo "Copying config files..."
cp ./docker/configs/settings_local.py ./ietf/settings_local.py
echo "Ensure all requirements.txt packages are installed..."
pip install -r requirements.txt
echo "Installing NPM packages..."
npm install --prefer-offline --no-audit
echo "Building static assets..."
npx parcel build
echo "Creating data directories..."
chmod +x ./docker/scripts/app-create-dirs.sh
./docker/scripts/app-create-dirs.sh
echo "Fetching latest coverage results file..."
curl -fsSL https://github.com/ietf-tools/datatracker/releases/latest/download/coverage.json -o release-coverage.json