#!/bin/bash
set -e

echo "Drop dummy ietf DB if it exists..."
dropdb -U django --if-exists ietf

# Extensions and search paths will be loaded from the dump
echo "Import DB dump into ietf..."
pg_restore --clean --if-exists --create --no-owner -U django -d postgres ietf.dump

echo "Done!"
