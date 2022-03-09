#!/bin/bash

echo "Installing NPM dependencies..."
npm install

echo "Building bootstrap 3 assets..."
cd bootstrap
npm install -g grunt-cli
npm install
grunt dist
cp -r dist/. ../ietf/static/ietf/bootstrap/
cd ..