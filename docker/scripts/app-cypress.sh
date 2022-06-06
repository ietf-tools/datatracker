#!/bin/bash

WORKSPACEDIR="/workspace"

pushd .
cd $WORKSPACEDIR

echo "Starting datatracker server..."
ietf/manage.py runserver 0.0.0.0:8000 --settings=settings_local > /dev/null 2>&1 &
serverPID=$!

echo "Waiting for server to come online ..."
/usr/local/bin/wait-for localhost:8000 -- echo "Server ready"

echo "Run dbus process to silence warnings..."
sudo mkdir -p /run/dbus
sudo dbus-daemon --system &> /dev/null

echo "Starting JS tests..."
yarn cypress

kill $serverPID
popd
