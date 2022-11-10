#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username postgres --dbname postgres <<-EOSQL
	CREATE USER django PASSWORD 'RkTkDPFnKpko';
	CREATE DATABASE ietf;
	GRANT ALL PRIVILEGES ON DATABASE ietf TO django;
    ALTER USER django set search_path=ietf_utf8,django,public;
EOSQL
