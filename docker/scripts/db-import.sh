#!/bin/bash
set -e

echo "Drop dummy datatracker DB if it exists..."
dropdb -U django --if-exists datatracker

# Extensions and search paths will be loaded from the dump
echo "Import DB dump into datatracker..."
pg_restore --clean --if-exists --create --no-owner -U django -d postgres datatracker.dump
echo "alter role django set search_path=datatracker,django,public;" | psql -U django -d datatracker

echo "Done!"
