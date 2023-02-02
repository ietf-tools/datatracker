#!/bin/bash
set -e

echo "Drop dummy ietf DB if it exists..."
dropdb -U django --if-exists ietf

echo "Create new ietf DB..."
createdb -U django ietf

echo "Enable citext extension on ietf DB..."
psql -U django -d ietf -v ON_ERROR_STOP=1 -c '\x' -c 'CREATE EXTENSION citext;'

echo "Import DB dump into ietf..."
pg_restore -U django -d ietf ietf.dump

echo "Set schema search path for user django..."
psql -U django -d ietf -v ON_ERROR_STOP=1 -c '\x' -c 'ALTER USER django set search_path=ietf_utf8,django,public;'

echo "Done!"
