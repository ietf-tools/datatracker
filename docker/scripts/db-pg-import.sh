#!/bin/bash
set -e

pg_restore -U django -C -d ietf ietf.dump
