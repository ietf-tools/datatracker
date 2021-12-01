#!/bin/bash

WORKSPACEDIR="/root/src"

pushd .
cd $WORKSPACEDIR
echo "Installing NPM dependencies..."
npm install --silent

echo "Starting datatracker server..."
ietf/manage.py runserver 0.0.0.0:8000 --settings=settings_local > /dev/null 2>&1 &
serverPID=$!

echo "Waiting for server to come online ..."
wget -qO- https://raw.githubusercontent.com/eficode/wait-for/v2.1.3/wait-for | sh -s -- localhost:8000 -- echo "Server ready"

echo "Run dbus process to silence warnings..."
sudo mkdir -p /run/dbus
sudo dbus-daemon --system &> /dev/null

echo "Starting JS tests..."
npx cypress run

kill $serverPID
popd