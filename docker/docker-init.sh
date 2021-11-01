#!/bin/bash

MYSQLDIR=/var/lib/mysql

if [ ! -d "$MYSQLDIR" ]; then
    echo "WARNING: Expected the directory $MYSQLDIR to exist."
    exit 1
fi

service rsyslog start

if [ -z "$(ls -A $MYSQLDIR/mysql 2>/dev/null)" ]; then
    can=$(date -r /mysql +%s)
    now=$(date +%s)
    age=$((($now - $can)/86400))
    echo "NOTE: Database empty; populating it from canned snapshot ($age days old)"
    echo "      This will take a little while..."
    cp -r /mysql/* $MYSQLDIR
fi

service mariadb start

if ! service mariadb status; then
    echo "ERROR: MySQL didn't start. Here are some possible causes:"
    echo "-------------------------------------------------------------------"
    grep mysqld /var/log/syslog
    echo "-------------------------------------------------------------------"
    echo "Such errors are usually due to a corrupt or outdated database."
    echo "Remove your local database and let the image install a clean copy."
    exit 1
fi

if [ ! -f /root/src/ietf/settings_local.py ]; then
    echo "Setting up a default settings_local.py ..."
    cp /root/src/docker/settings_local.py /root/src/ietf/settings_local.py
fi

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

python -m smtpd -n -c DebuggingServer localhost:2025 &
echo

if [ -z "$*" ]; then
    echo "You can execute arbitrary commands now, e.g.,"
    echo
    echo "    ietf/manage.py runserver 0.0.0.0:8000"
    echo
    echo "to start a development instance of the Datatracker."
    echo
    bash
else
    echo "Executing \"$*\" and stopping container."
    echo
    bash -c "$*"
fi

service mariadb stop
service rsyslog stop