#!/bin/bash -e

echo "Running Datatracker migrations..."
./ietf/manage.py migrate --settings=settings_local

# Check whether the blobdb database exists - inspectdb will return a false
# status if not.
if ./ietf/manage.py inspectdb --database blobdb > /dev/null 2>&1; then
    echo "Running Blobdb migrations ..."
    ./ietf/manage.py migrate --settings=settings_local --database=blobdb
fi

echo "Done!"
