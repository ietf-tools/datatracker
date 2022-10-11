#!/bin/bash

echo "Fixing permissions..."
chmod -R 777 ./
echo "Ensure all requirements.txt packages are installed..."
pip --disable-pip-version-check --no-cache-dir install -r requirements.txt
echo "Compiling native node packages..."
yarn rebuild
echo "Building static assets..."
yarn build
yarn legacy:build
echo "Creating data directories..."
chmod +x ./docker/scripts/app-create-dirs.sh
./docker/scripts/app-create-dirs.sh

./ietf/manage.py check
if ./ietf/manage.py showmigrations | grep "\[ \] 0003_pause_to_change_use_tz"; then
    if grep "USE_TZ" ./ietf/settings_local.py; then
        cat ./ietf/settings_local.py | sed 's/USE_TZ.*$/USE_TZ = False/' > /tmp/settings_local.py && mv /tmp/settings_local.py ./ietf/settings_local.py
    else
        echo "USE_TZ = False" >> ./ietf/settings_local.py
    fi
    # This is expected to exit non-zero at the pause
    /usr/local/bin/python ./ietf/manage.py migrate  || true
    cat ./ietf/settings_local.py | sed 's/USE_TZ.*$/USE_TZ = True/' > /tmp/settings_local.py && mv /tmp/settings_local.py ./ietf/settings_local.py
    /usr/local/bin/python ./ietf/manage.py migrate

else
    if grep "USE_TZ" ./ietf/settings_local.py; then
        cat ./ietf/settings_local.py | sed 's/USE_TZ.*$/USE_TZ = True/' > /tmp/settings_local.py && mv /tmp/settings_local.py ./ietf/settings_local.py
    else
        echo "USE_TZ = True" >> ./ietf/settings_local.py
    /usr/local/bin/python ./ietf/manage.py migrate
    fi
fi
