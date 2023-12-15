#!/bin/bash

WORKSPACEDIR="/workspace"

sudo service rsyslog start &>/dev/null

# Add /workspace as a safe git directory
git config --global --add safe.directory /workspace

# Turn off git info in zsh prompt (causes slowdowns)
git config oh-my-zsh.hide-info 1

# Fix ownership of volumes
echo "Fixing volumes ownership..."
sudo chown -R dev:dev "$WORKSPACEDIR/.parcel-cache"
sudo chown -R dev:dev "$WORKSPACEDIR/__pycache__"
sudo chown -R dev:dev "$WORKSPACEDIR/.vite"
sudo chown -R dev:dev "$WORKSPACEDIR/.yarn/unplugged"
sudo chown dev:dev "/assets"

# Run nginx
echo "Starting nginx..."
sudo nginx

# Build node packages that requrie native compilation
echo "Compiling native node packages..."
yarn rebuild

# Silence Browserlist warnings
export BROWSERSLIST_IGNORE_OLD_DATA=1

# Generate static assets
echo "Building static assets... (this could take a minute or two)"
yarn build
yarn legacy:build

# Copy config files if needed
cp $WORKSPACEDIR/docker/configs/settings_postgresqldb.py $WORKSPACEDIR/ietf/settings_postgresqldb.py

if [ ! -f "$WORKSPACEDIR/ietf/settings_local.py" ]; then
    echo "Setting up a default settings_local.py ..."
else
    echo "Renaming existing ietf/settings_local.py to ietf/settings_local.py.bak"
    mv -f $WORKSPACEDIR/ietf/settings_local.py $WORKSPACEDIR/ietf/settings_local.py.bak
fi
cp $WORKSPACEDIR/docker/configs/settings_local.py $WORKSPACEDIR/ietf/settings_local.py

if [ ! -f "$WORKSPACEDIR/ietf/settings_local_debug.py" ]; then
    echo "Setting up a default settings_local_debug.py ..."
else
    echo "Renaming existing ietf/settings_local_debug.py to ietf/settings_local_debug.py.bak"
    mv -f $WORKSPACEDIR/ietf/settings_local_debug.py $WORKSPACEDIR/ietf/settings_local_debug.py.bak
fi
cp $WORKSPACEDIR/docker/configs/settings_local_debug.py $WORKSPACEDIR/ietf/settings_local_debug.py

if [ ! -f "$WORKSPACEDIR/ietf/settings_local_vite.py" ]; then
    echo "Setting up a default settings_local_vite.py ..."
else
    echo "Renaming existing ietf/settings_local_vite.py to ietf/settings_local_vite.py.bak"
    mv -f $WORKSPACEDIR/ietf/settings_local_vite.py $WORKSPACEDIR/ietf/settings_local_vite.py.bak
fi
cp $WORKSPACEDIR/docker/configs/settings_local_vite.py $WORKSPACEDIR/ietf/settings_local_vite.py

# Create data directories

echo "Creating data directories..."
chmod +x ./docker/scripts/app-create-dirs.sh
./docker/scripts/app-create-dirs.sh

# Download latest coverage results file

echo "Downloading latest coverage results file..."
curl -fsSL https://github.com/ietf-tools/datatracker/releases/download/baseline/coverage.json -o release-coverage.json

# Wait for DB container

if [ -n "$EDITOR_VSCODE" ]; then
    echo "Waiting for DB container to come online ..."
    /usr/local/bin/wait-for db:5432 -- echo "PostgreSQL ready"
fi

# Run memcached

echo "Starting memcached..."
/usr/bin/memcached -u dev -d

# Initial checks

echo "Running initial checks..."
/usr/local/bin/python $WORKSPACEDIR/ietf/manage.py check --settings=settings_local

# Migrate, adjusting to what the current state of the underlying database might be:

/usr/local/bin/python $WORKSPACEDIR/ietf/manage.py migrate --fake-initial --settings=settings_local

if [ -z "$EDITOR_VSCODE" ]; then
    CODE=0
    python -m smtpd -n -c DebuggingServer localhost:2025 &
    if [ -z "$*" ]; then
        echo "-----------------------------------------------------------------"
        echo "Ready!"
        echo "-----------------------------------------------------------------"
        echo
        echo "You can execute arbitrary commands now, e.g.,"
        echo
        echo "    ietf/manage.py runserver 8001"
        echo
        echo "to start a development instance of the Datatracker."
        echo
        echo "    ietf/manage.py test --settings=settings_test"
        echo
        echo "to run all the python tests."
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
