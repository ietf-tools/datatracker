#!/bin/bash

WORKSPACEDIR="/workspace"

sudo service rsyslog start &>/dev/null

# Turn off git info in zsh prompt (causes slowdowns)
git config oh-my-zsh.hide-info 1

# Fix ownership of volumes
echo "Fixing volumes ownership..."
sudo chown -R dev:dev "$WORKSPACEDIR/.parcel-cache"
sudo chown -R dev:dev "$WORKSPACEDIR/__pycache__"
sudo chown -R dev:dev "$WORKSPACEDIR/.vite"
sudo chown -R dev:dev "$WORKSPACEDIR/.yarn/unplugged"
sudo chown dev:dev "/assets"

echo "Fix chromedriver /dev/shm permissions..."
sudo chmod 1777 /dev/shm

# Build node packages that requrie native compilation
echo "Compiling native node packages..."
yarn rebuild

# Generate static assets
echo "Building static assets... (this could take a minute or two)"
yarn build
yarn legacy:build

# Copy config files if needed
if [ ! -f "$WORKSPACEDIR/ietf/settings_mysqldb.py" ]; then
    cp $WORKSPACEDIR/docker/configs/settings_mysqldb.py $WORKSPACEDIR/ietf/settings_mysqldb.py
fi
if [ ! -f "$WORKSPACEDIR/ietf/settings_postgresqldb.py" ]; then
    cp $WORKSPACEDIR/docker/configs/settings_postgresqldb.py $WORKSPACEDIR/ietf/settings_postgresqldb.py
fi

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

if [ ! -f "$WORKSPACEDIR/ietf/settings_local_vite.py" ]; then
    echo "Setting up a default settings_local_vite.py ..."
    cp $WORKSPACEDIR/docker/configs/settings_local_vite.py $WORKSPACEDIR/ietf/settings_local_vite.py
else
    echo "Using existing ietf/settings_local_vite.py file"
    if ! cmp -s $WORKSPACEDIR/docker/configs/settings_local_vite.py $WORKSPACEDIR/ietf/settings_local_vite.py; then
        echo "NOTE: Differences detected compared to docker/configs/settings_local_vite.py!"
        echo "We'll assume you made these deliberately."
    fi
fi

# Recondition settings to make changing databases easier. (Remember that we may have developers starting with settings_local from earlier work)
    python docker/scripts/db-include-fix.py
    cat $WORKSPACEDIR/ietf/settings_local.py | sed 's/from ietf.settings_postgresqldb import DATABASES/from ietf.settings_mysqldb import DATABASES/' > /tmp/settings_local.py && mv /tmp/settings_local.py $WORKSPACEDIR/ietf/settings_local.py

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
    /usr/local/bin/wait-for db:3306 -- echo "MariaDB ready"
    /usr/local/bin/wait-for pgdb:5432 -- echo "Postgresql ready"
fi

# Run memcached

echo "Starting memcached..."
/usr/bin/memcached -u dev -d

# Initial checks

echo "Running initial checks..."
/usr/local/bin/python $WORKSPACEDIR/ietf/manage.py check --settings=settings_local

# Migrate, adjusting to what the current state of the underlying database might be:

if ietf/manage.py showmigrations | grep "\[ \] 0003_pause_to_change_use_tz"; then
    if grep "USE_TZ" $WORKSPACEDIR/ietf/settings_local.py; then
        cat $WORKSPACEDIR/ietf/settings_local.py | sed 's/USE_TZ.*$/USE_TZ = False/' > /tmp/settings_local.py && mv /tmp/settings_local.py $WORKSPACEDIR/ietf/settings_local.py
    else
        echo "USE_TZ = False" >> $WORKSPACEDIR/ietf/settings_local.py
    fi
    # This is expected to exit non-zero at the pause
    /usr/local/bin/python $WORKSPACEDIR/ietf/manage.py migrate --settings=settings_local || true
    cat $WORKSPACEDIR/ietf/settings_local.py | sed 's/USE_TZ.*$/USE_TZ = True/' > /tmp/settings_local.py && mv /tmp/settings_local.py $WORKSPACEDIR/ietf/settings_local.py
    # This is also expected to exit non-zero at the 2nd pause
    echo "DEBUGGING pt 1 - this should say mysqldb"
    grep "DATA" $WORKSPACEDIR/ietf/settings_local.py
    /usr/local/bin/python $WORKSPACEDIR/ietf/manage.py migrate --settings=settings_local || true
    # More migrations after the move to postgres below.

else
    if grep "USE_TZ" $WORKSPACEDIR/ietf/settings_local.py; then
        cat $WORKSPACEDIR/ietf/settings_local.py | sed 's/USE_TZ.*$/USE_TZ = True/' > /tmp/settings_local.py && mv /tmp/settings_local.py $WORKSPACEDIR/ietf/settings_local.py
    else
        echo "USE_TZ = True" >> $WORKSPACEDIR/ietf/settings_local.py
    /usr/local/bin/python $WORKSPACEDIR/ietf/manage.py migrate --settings=settings_local
    fi
fi

# We may be starting with a post 9.0.0 deploy dump, so run the migrations again before switching engines to catch any pre-postgres migrations that may be merged in from main post 9.0.0 (and any that are specific to feat/postgres that need to run before we switch engines)
/usr/local/bin/python $WORKSPACEDIR/ietf/manage.py migrate --settings=settings_local || true

echo "DEBUGGING pt 2 - this should say mysqldb"
grep "DATA" $WORKSPACEDIR/ietf/settings_local.py
cat $WORKSPACEDIR/ietf/settings_local.py | sed 's/from ietf.settings_mysqldb import DATABASES/from ietf.settings_postgresqldb import DATABASES/' > /tmp/settings_local.py && mv /tmp/settings_local.py $WORKSPACEDIR/ietf/settings_local.py
echo "DEBUGGING pt 3 - this should say postgresdb"
grep "DATA" $WORKSPACEDIR/ietf/settings_local.py

# Now transfer the migrated database from mysql to postgres unless that's already happened.
if psql -U django -h pgdb -d ietf -c "\dt" 2>&1 | grep -q "Did not find any relations."; then
    cat << EOF > cast.load
LOAD DATABASE
FROM mysql://django:RkTkDPFnKpko@db/ietf_utf8
INTO postgresql://django:RkTkDPFnKpko@pgdb/ietf
CAST type varchar to text drop typemod;
EOF
    time pgloader --verbose --logfile=ietf_pgloader.run --summary=ietf_pgloader.summary cast.load
    rm cast.load
    /usr/local/bin/python $WORKSPACEDIR/ietf/manage.py migrate --settings=settings_local
fi

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
        echo "    ietf/manage.py runserver 0.0.0.0:8000"
        echo
        echo "to start a development instance of the Datatracker."
        echo
        echo "    ietf/manage.py test --settings=settings_sqlitetest"
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
