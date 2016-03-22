#!/bin/bash

echo "Gathering info ..."
MYSQLDIR="$(mysqld --verbose --help 2>/dev/null | awk '$1 == "datadir" { print $2; exit }')"
if [ ! "$USER" ]; then
    echo "Environment variable USER is not set -- will set USER='django'."
    USER="django"
fi
if [ ! "$TAG" ]; then
    echo "Environment variable TAG is not set -- will set TAG='datatracker'."
    TAG="datatracker"
fi

echo "Checking if MySQL base data exists ..."
if [ ! -d $MYSQLDIR/mysql ]; then
    echo "WARNING: Expected the directory $MYSQLDIR/mysql/ to exist -- have you downloaded and unpacked the IETF binary database tarball?"
fi

echo "Setting up the 'mysql' user for database file access ..."
MYSQL_TARGET_GID=$(stat -c "%g" $MYSQLDIR/mysql)
if ! grep -q ":$MYSQL_TARGET_GID:$" /etc/group; then
    groupadd -g $MYSQL_TARGET_GID mysqldata
fi
usermod -a -G $MYSQL_TARGET_GID mysql

echo "Checking if MySQL is running ..."
if ! /etc/init.d/mysql status; then
    echo "Starting mysql ..."
    /etc/init.d/mysql start
fi

# Give debian-sys-maint access, to avoid complaints later
mysql mysql <<< "GRANT ALL PRIVILEGES on *.* TO 'debian-sys-maint'@'localhost' IDENTIFIED BY '$(awk '/^password/ {print $3; exit}' /etc/mysql/debian.cnf )' WITH GRANT OPTION; FLUSH PRIVILEGES;"

echo "Checking if the IETF database exists at $MYSQLDIR ..."
if [ ! -d $MYSQLDIR/ietf_utf8 ]; then
    if [ -z "$DATADIR" ]; then
	echo "DATADIR is not set, but the IETF database needs to be set up -- can't continue, exiting the docker init script."
	exit 1
    fi
    ls -l $MYSQLDIR

    if ! /etc/init.d/mysql status; then
	echo "Didn't find the IETF database, but can't set it up either, as MySQL isn't running."
    else
	echo "Creating database ..."
	mysqladmin -u root --default-character-set=utf8 create ietf_utf8

	echo "Setting up permissions ..."
	mysql -u root ietf_utf8 <<< "GRANT ALL PRIVILEGES ON ietf_utf8.* TO django@localhost IDENTIFIED BY 'RkTkDPFnKpko'; FLUSH PRIVILEGES;"

	echo "Fetching database ..."       
	DUMPDIR=/home/$USER/$DATADIR
	wget -N -P $DUMPDIR http://www.ietf.org/lib/dt/sprint/ietf_utf8.sql.gz

	echo "Loading database ..."
	gunzip < $DUMPDIR/ietf_utf8.sql.gz \
	    | pv --progress --bytes --rate --eta --cursor --size $(gzip --list --quiet $DUMPDIR/ietf_utf8.sql.gz | awk '{ print $2 }') \
	    | sed -e 's/ENGINE=MyISAM/ENGINE=InnoDB/' \
	    | mysql --user=django --password=RkTkDPFnKpko -s -f ietf_utf8 \
	    && rm /tmp/ietf_utf8.sql.gz
    fi
fi

if ! id -u "$USER" &> /dev/null; then
    echo "Creating user '$USER' ..."
    useradd -s /bin/bash -G staff,sudo $USER
    echo "$USER:$USER" | chpasswd
fi

VIRTDIR="/opt/home/$USER/$TAG"
echo "Checking that there's a virtual environment for $TAG ..."
if [ ! -f $VIRTDIR/bin/activate ]; then
    echo "Setting up python virtualenv at /opt/home/$USER ..."
    mkdir -p /opt/home/$USER
    chown $USER /opt/home/$USER
    mkdir $VIRTDIR
    virtualenv --system-site-packages $VIRTDIR
    cat $VIRTDIR/bin/activate >> /etc/bash.bashrc
    cat /usr/local/share/datatracker/setprompt >> /etc/bash.bashrc 
fi

echo "Activating the virtual python environment ..."
. $VIRTDIR/bin/activate

if ! python -c "import django"; then
    echo "Installing requirements ..."
    pip install -r /usr/local/share/datatracker/requirements.txt
fi

if [ ! -f $VIRTDIR/lib/site-python/settings_local.py ]; then
    echo "Setting up a default settings_local.py ..."
    mkdir -p $VIRTDIR/lib/site-python/
    cp /usr/local/share/datatracker/settings_local.py $VIRTDIR/lib/site-python/
fi

for sub in test/id/ test/staging/ test/archive/; do
    dir="/home/$USER/$CWD/$sub"
    if [ ! -d "$dir"  ]; then
	echo "Creating dir $dir"
	mkdir -p "$dir";
    fi
done

for sub in					\
	nomcom_keys/public_keys			\
	developers/ietf-ftp			\
	developers/ietf-ftp/internet-drafts	\
	developers/ietf-ftp/rfc			\
	developers/ietf-ftp/charter		\
	developers/ietf-ftp/status-changes	\
	developers/ietf-ftp/conflict-reviews	\
	developers/www6s			\
	developers/www6s/staging		\
	developers/www6s/wg-descriptions	\
	developers/www6s/proceedings		\
	developers/www6/			\
	developers/www6/iesg			\
	developers/www6/iesg/evaluation		\
	; do
    dir="/home/$USER/$CWD/data/$sub"
    if [ ! -d "$dir"  ]; then
	echo "Creating dir $dir"
	mkdir -p "$dir";
    fi
done

if [ ! -f "/home/$USER/$CWD/test/data/draft-aliases" ]; then
    echo "Generating draft aliases ..."
    ietf/bin/generate-draft-aliases }
fi

if [ ! -f "/home/$USER/$CWD/test/data/group-aliases" ]; then
    echo "Generating group aliases ..."
    ietf/bin/generate-wg-aliases }
fi

chown -R $USER /opt/home/$USER

cd "/home/$USER/$CWD" || cd "/home/$USER/"

echo "Done!"

su $USER
