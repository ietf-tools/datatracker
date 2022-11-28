#!/bin/bash

echo "Fixing permissions..."
chmod -R 777 ./
echo "Ensure all requirements.txt packages are installed..."
pip --disable-pip-version-check --no-cache-dir install -r requirements.txt
echo "Creating data directories..."
chmod +x ./app-create-dirs.sh
./app-create-dirs.sh
echo "Running Datatracker checks..."
./ietf/manage.py check

# Migrate, adjusting to what the current state of the underlying database might be:
WORKSPACEDIR=.
if ietf/manage.py showmigrations | grep "\[ \] 0003_pause_to_change_use_tz"; then
    if grep "USE_TZ" $WORKSPACEDIR/ietf/settings_local.py; then
        cat $WORKSPACEDIR/ietf/settings_local.py | sed 's/USE_TZ.*$/USE_TZ = False/' > /tmp/settings_local.py && mv /tmp/settings_local.py $WORKSPACEDIR/ietf/settings_local.py
    else
        echo "USE_TZ = False" >> $WORKSPACEDIR/ietf/settings_local.py
    fi
    echo "Running Datatracker migrations with USE_TZ = False..."
    # This is expected to exit non-zero at the pause
    /usr/local/bin/python $WORKSPACEDIR/ietf/manage.py migrate --settings=settings_local || true
    cat $WORKSPACEDIR/ietf/settings_local.py | sed 's/USE_TZ.*$/USE_TZ = True/' > /tmp/settings_local.py && mv /tmp/settings_local.py $WORKSPACEDIR/ietf/settings_local.py
    echo "Running Datatracker migrations with USE_TZ = True..."
    /usr/local/bin/python $WORKSPACEDIR/ietf/manage.py migrate --settings=settings_local

else
    if grep "USE_TZ" $WORKSPACEDIR/ietf/settings_local.py; then
        cat $WORKSPACEDIR/ietf/settings_local.py | sed 's/USE_TZ.*$/USE_TZ = True/' > /tmp/settings_local.py && mv /tmp/settings_local.py $WORKSPACEDIR/ietf/settings_local.py
    else
        echo "USE_TZ = True" >> $WORKSPACEDIR/ietf/settings_local.py
    echo "Running Datatracker migrations..."
    /usr/local/bin/python $WORKSPACEDIR/ietf/manage.py migrate --settings=settings_local
    fi
fi

echo "Starting Datatracker..."
./ietf/manage.py runserver 0.0.0.0:8000 --settings=settings_local
