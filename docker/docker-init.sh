#!/bin/bash

MYSQLDIR=/var/lib/mysql

if [ ! -d "$MYSQLDIR" ]; then
    echo "WARNING: Expected the directory $MYSQLDIR to exist."
    exit 1
fi

service rsyslog start

if [ -z "$(ls -A $MYSQLDIR/mysql 2>/dev/null)" ]; then
    echo "WARNING: Database seems to be empty."
    mysql_install_db > /dev/null || exit 1
fi

service mariadb start

if ! service mariadb status; then
    echo "ERROR: MySQL isn't running."
    grep mysqld /var/log/syslog
    exit 1
fi

if [ ! -f /root/src/ietf/settings_local.py ]; then
    echo "Setting up a default settings_local.py ..."
    cp /root/src/docker/settings_local.py /root/src/ietf/settings_local.py
fi

if [ ! -d $MYSQLDIR/ietf_utf8 ]; then
    echo "WARNING: IETF database seems to be missing; populating it from dump."
    mysqladmin -u root --default-character-set=utf8 create ietf_utf8
    pushd /mariadb-sys-master || exit
    mysql -u root < sys_10.sql
    popd || exit
    mysql -u root ietf_utf8 <<< "GRANT ALL PRIVILEGES ON *.* TO django@localhost IDENTIFIED BY 'RkTkDPFnKpko'; FLUSH PRIVILEGES;"
    /root/src/docker/updatedb
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
    bash
else
    bash -c "$*"
fi

service mariadb stop
service rsyslog stop