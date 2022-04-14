#!/bin/bash

echo "Installing NPM dependencies..."
npm install

echo "Packaging static assets..."
npx parcel build
