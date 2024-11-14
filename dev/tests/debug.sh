#!/bin/bash

# This script recreate the same environment used during tests on GitHub Actions
# and drops you into a terminal at the point where the actual tests would be run.
#
# Refer to https://github.com/ietf-tools/datatracker/blob/main/.github/workflows/tests.yml#L47-L66
# for the commands to run next.
#
# Simply type "exit" + ENTER to exit and shutdown this test environment.

echo "Fetching latest images..."
docker pull ghcr.io/ietf-tools/datatracker-app-base:latest
docker pull ghcr.io/ietf-tools/datatracker-db:latest
echo "Starting containers..."
docker compose -f docker-compose.debug.yml -p dtdebug --compatibility up -d
echo "Copying working directory into container..."
docker compose -p dtdebug cp ../../. app:/__w/datatracker/datatracker/
echo "Run prepare script..."
docker compose -p dtdebug exec app chmod +x ./dev/tests/prepare.sh
docker compose -p dtdebug exec app sh ./dev/tests/prepare.sh
docker compose -p dtdebug exec app /usr/local/bin/wait-for db:5432 -- echo "DB ready"
echo "================================================================="
echo "Launching zsh terminal:"
docker compose -p dtdebug exec app /bin/zsh
echo "Shutting down containers..."
docker compose -p dtdebug down -v
