#!/bin/bash
set -e

dropdb -U django ietf
pg_restore -U django -C -d ietf ietf.dump
