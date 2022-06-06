#!/bin/bash

WORKSPACEDIR="/workspace"

sudo service rsyslog start &>/dev/null

# Fix ownership of volumes
echo "Fixing volumes ownership..."
sudo chown -R dev:dev "$WORKSPACEDIR/.parcel-cache"
sudo chown -R dev:dev "$WORKSPACEDIR/__pycache__"
sudo chown dev:dev "/assets"

echo "Fix chromedriver /dev/shm permissions..."
sudo chmod 1777 /dev/shm

# Build node packages that requrie native compilation
echo "Compiling native node packages..."
yarn rebuild

# Generate static assets
echo "Building static assets... (this could take a minute or two)"
yarn build

# Copy config files if needed

if [ ! -f "$WORKSPACEDIR/ietf/settings_local.py" ]; then
    echo "Setting up a default settings_local.py ..."
    cp $WORKSPACEDIR/docker/configs/settings_local.py $WORKSPACEDIR/ietf/settings_local.py
else
    echo "Using existing ietf/settings_local.py file"
    if ! cmp -s $WORKSPACEDIR/docker/configs/settings_local.py $WORKSPACEDIR/ietf/settings_local.py; then
        echo "NOTE: Differences detected compared to docker/configs/settings_local.py!"
        echo "We'll assume you made these deliberately."
    fi
fi

if [ ! -f "$WORKSPACEDIR/ietf/settings_local_debug.py" ]; then
    echo "Setting up a default settings_local_debug.py ..."
    cp $WORKSPACEDIR/docker/configs/settings_local_debug.py $WORKSPACEDIR/ietf/settings_local_debug.py
else
    echo "Using existing ietf/settings_local_debug.py file"
    if ! cmp -s $WORKSPACEDIR/docker/configs/settings_local_debug.py $WORKSPACEDIR/ietf/settings_local_debug.py; then
        echo "NOTE: Differences detected compared to docker/configs/settings_local_debug.py!"
        echo "We'll assume you made these deliberately."
    fi
fi

if [ ! -f "$WORKSPACEDIR/ietf/settings_local_sqlitetest.py" ]; then
    echo "Setting up a default settings_local_sqlitetest.py ..."
    cp $WORKSPACEDIR/docker/configs/settings_local_sqlitetest.py $WORKSPACEDIR/ietf/settings_local_sqlitetest.py
else
    echo "Using existing ietf/settings_local_sqlitetest.py file"
    if ! cmp -s $WORKSPACEDIR/docker/configs/settings_local_sqlitetest.py $WORKSPACEDIR/ietf/settings_local_sqlitetest.py; then
        echo "NOTE: Differences detected compared to docker/configs/settings_local_sqlitetest.py!"
        echo "We'll assume you made these deliberately."
    fi
fi

# Create data directories

echo "Creating data directories..."
chmod +x ./docker/scripts/app-create-dirs.sh
./docker/scripts/app-create-dirs.sh

# Download latest coverage results file

echo "Downloading latest coverage results file..."
curl -fsSL https://github.com/ietf-tools/datatracker/releases/latest/download/coverage.json -o release-coverage.json

# Wait for DB container

if [ -n "$EDITOR_VSCODE" ]; then
    echo "Waiting for DB container to come online ..."
    /usr/local/bin/wait-for localhost:3306 -- echo "DB ready"
fi

# Run memcached

echo "Starting memcached..."
/usr/bin/memcached -u dev -d

# Initial checks

echo "Running initial checks..."
/usr/local/bin/python $WORKSPACEDIR/ietf/manage.py check --settings=settings_local
# /usr/local/bin/python $WORKSPACEDIR/ietf/manage.py migrate --settings=settings_local

echo "-----------------------------------------------------------------"
echo "Done!"
echo "-----------------------------------------------------------------"

if [ -z "$EDITOR_VSCODE" ]; then
    CODE=0
    python -m smtpd -n -c DebuggingServer localhost:2025 &
    if [ -z "$*" ]; then
        echo
        echo "You can execute arbitrary commands now, e.g.,"
        echo
        echo "    ietf/manage.py check && ietf/manage.py runserver 0.0.0.0:8000"
        echo
        echo "to start a development instance of the Datatracker."
        echo
        echo "    ietf/manage.py test --settings=settings_sqlitetest"
        echo
        echo "to run all the tests."
        echo
        zsh
    else
        echo "Executing \"$*\" and stopping container."
        echo
        zsh -c "$*"
        CODE=$?
    fi
    sudo service rsyslog stop
    exit $CODE
fi
