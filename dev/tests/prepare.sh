#!/bin/bash

echo "Running containers:"
docker ps -a
echo "Fixing permissions..."
chmod -R 777 ./
echo "Copying config files..."
cp ./dev/tests/settings_local.py ./ietf/settings_local.py
echo "Ensure all requirements.txt packages are installed..."
pip --disable-pip-version-check --no-cache-dir install -r requirements.txt
echo "Installing idnits3..."
npm install -g --prefix /usr/local/idnits3 @ietf-tools/idnits@3.1.0
ln -sf /usr/local/idnits3/bin/idnits /usr/local/bin/idnits3
idnits3 --version
echo "Compiling native node packages..."
npm ci
echo "Building static assets..."
npm run build
npm run legacy:build
echo "Creating data directories..."
chmod +x ./docker/scripts/app-create-dirs.sh
./docker/scripts/app-create-dirs.sh
echo "Fetching latest coverage results file..."
curl -fsSL https://github.com/ietf-tools/datatracker/releases/download/baseline/coverage.json -o release-coverage.json
psql -U django -h db -d datatracker -v ON_ERROR_STOP=1 -c '\x' -c 'ALTER USER django set search_path=datatracker,public;'
