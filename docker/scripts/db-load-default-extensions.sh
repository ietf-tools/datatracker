#!/bin/bash
set -e

psql -U django -d template1 -v ON_ERROR_STOP=1 -c 'CREATE EXTENSION IF NOT EXISTS citext;'

