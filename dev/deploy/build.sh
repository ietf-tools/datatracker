#!/bin/bash

echo "Compiling native node packages..."
yarn rebuild
echo "Packaging static assets..."
if [ "${SHOULD_DEPLOY}" = "true" ]; then
    yarn build --base=https://www.ietf.org/lib/dt/$PKG_VERSION/
else
    yarn build
fi
yarn legacy:build
