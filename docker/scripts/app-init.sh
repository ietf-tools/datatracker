#!/bin/bash

WORKSPACEDIR="/root/src"

service rsyslog start

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

# Create assets directories

for sub in					\
    test/id \
    test/staging \
    test/archive \
    test/rfc \
    test/media \
    test/wiki/ietf \
	data/nomcom_keys/public_keys			\
	data/developers/ietf-ftp			\
	data/developers/ietf-ftp/bofreq		\
	data/developers/ietf-ftp/charter		\
	data/developers/ietf-ftp/conflict-reviews	\
	data/developers/ietf-ftp/internet-drafts	\
	data/developers/ietf-ftp/rfc			\
	data/developers/ietf-ftp/status-changes	\
	data/developers/ietf-ftp/yang/catalogmod	\
	data/developers/ietf-ftp/yang/draftmod	\
	data/developers/ietf-ftp/yang/ianamod	\
	data/developers/ietf-ftp/yang/invalmod	\
	data/developers/ietf-ftp/yang/rfcmod		\
	data/developers/www6s			\
	data/developers/www6s/staging		\
	data/developers/www6s/wg-descriptions	\
	data/developers/www6s/proceedings		\
	data/developers/www6/			\
	data/developers/www6/iesg			\
	data/developers/www6/iesg/evaluation		\
	; do
    dir="/root/src/$sub"
    if [ ! -d "$dir"  ]; then
    	echo "Creating dir $dir"
	    mkdir -p "$dir";
    fi
done

# Wait for DB container
if [ -n "$EDITOR_VSCODE" ]; then
    echo "Waiting for DB container to come online ..."
    wget -qO- https://raw.githubusercontent.com/eficode/wait-for/v2.1.3/wait-for | sh -s -- localhost:3306 -- echo "DB ready"
fi

# Initial checks

echo "Running initial checks..."
/usr/local/bin/python $WORKSPACEDIR/ietf/manage.py check --settings=settings_local
# /usr/local/bin/python $WORKSPACEDIR/ietf/manage.py migrate --settings=settings_local

echo "Done!"

if [ -z "$EDITOR_VSCODE" ]; then
    python -m smtpd -n -c DebuggingServer localhost:2025 &
    if [ -z "$*" ]; then
        echo
        echo "You can execute arbitrary commands now, e.g.,"
        echo
        echo "    ietf/manage.py check && ietf/manage.py runserver 0.0.0.0:8000"
        echo
        echo "to start a development instance of the Datatracker."
        echo
        bash
    else
        echo "Executing \"$*\" and stopping container."
        echo
        bash -c "$*"
    fi
    service rsyslog stop
fi