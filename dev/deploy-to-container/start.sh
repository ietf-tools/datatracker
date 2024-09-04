#!/bin/bash

echo "Creating /test directories..."
for sub in \
    /test/id \
    /test/staging \
    /test/archive \
    /test/rfc \
    /test/media \
    /test/wiki/ietf \
    ; do
    if [ ! -d "$sub"  ]; then
        echo "Creating dir $sub"
        mkdir -p "$sub";
    fi
done
echo "Fixing permissions..."
chmod -R 777 ./
echo "Ensure all requirements.txt packages are installed..."
pip --disable-pip-version-check --no-cache-dir install -r requirements.txt
echo "Creating data directories..."
chmod +x ./app-create-dirs.sh
./app-create-dirs.sh

if [ -n "$PGHOST" ]; then
    echo "Altering PG search path..."
    psql -U django -h $PGHOST -d datatracker -v ON_ERROR_STOP=1 -c '\x' -c 'ALTER USER django set search_path=datatracker,public;'
fi

echo "Starting memcached..."
/usr/bin/memcached -d -u root

echo "Running Datatracker checks..."
./ietf/manage.py check

# Migrate, adjusting to what the current state of the underlying database might be:

echo "Running Datatracker migrations..."
/usr/local/bin/python ./ietf/manage.py migrate --settings=settings_local

echo "Starting Datatracker..."
./ietf/manage.py runserver 0.0.0.0:8000 --settings=settings_local
