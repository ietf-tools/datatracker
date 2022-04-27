#!/bin/bash

echo "Compiling native node packages..."
yarn rebuild
echo "Packaging static assets..."
yarn build
