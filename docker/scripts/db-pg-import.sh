#!/bin/bash
set -e

dropdb -U django --if-exists ietf
createdb -U django ietf
pg_restore -U django -d ietf ietf.dump
