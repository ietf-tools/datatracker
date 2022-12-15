#!/bin/bash
set -e

dropdb -U django --if-exists ietf
createdb -U django ietf
pg_restore -U django -d ietf ietf.dump
psql -U django -d ietf -v ON_ERROR_STOP=1 -c '\x' -c 'ALTER USER django set search_path=ietf_utf8,django,public;'
