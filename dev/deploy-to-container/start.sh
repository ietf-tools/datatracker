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

# On production, the blobdb tables are in a separate database. Manipulate migration
# history to ensure that they're created for the sandbox environment that runs it
# all from a single database.
echo "Ensuring blobdb relations exist..."
/usr/local/bin/python ./ietf/manage.py migrate --settings=settings_local --fake blobdb zero
if ! /usr/local/bin/python ./ietf/manage.py migrate --settings=settings_local blobdb; then
  # If we are restarting a sandbox, the migration may already have run and re-running
  # it will fail. Assume that happened and fake it.
  /usr/local/bin/python ./ietf/manage.py migrate --settings=settings_local --fake blobdb
fi

# Now run the migrations for real
echo "Running Datatracker migrations..."
/usr/local/bin/python ./ietf/manage.py migrate --settings=settings_local

echo "Starting Datatracker..."
./ietf/manage.py runserver 0.0.0.0:8000 --settings=settings_local
