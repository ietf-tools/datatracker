#!/bin/bash
set -e

dropdb -U django --if-exists ietf
pg_restore -U django -d ietf ietf.dump
