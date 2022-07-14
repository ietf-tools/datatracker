#!/bin/bash

echo "Compiling native node packages..."
yarn rebuild
echo "Packaging static assets..."
yarn build --base=https://www.ietf.org/lib/dt/$PKG_VERSION/
yarn legacy:build
