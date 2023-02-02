#!/bin/bash
set -e

echo "Drop dummy ietf DB if it exists..."
dropdb -U django --if-exists ietf

#echo "Create new ietf DB..."
#createdb -U django ietf
#
#echo "Enable citext extension..."
#psql -U django -d ietf -v ON_ERROR_STOP=1 -c '\x' -c 'CREATE EXTENSION IF NOT EXISTS citext;'
#
#echo "Set schema search path for user django..."
#psql -U django -d ietf -v ON_ERROR_STOP=1 -c '\x' -c 'ALTER USER django set search_path=ietf_utf8,django,public;'

echo "Import DB dump into ietf..."
pg_restore --clean --if-exists --create -U django -d ietf ietf.dump

#echo "Set schema search path for user django..."
#psql -U django -d ietf -v ON_ERROR_STOP=1 -c '\x' -c 'ALTER USER django set search_path=ietf_utf8,django,public;'

echo "Done!"
