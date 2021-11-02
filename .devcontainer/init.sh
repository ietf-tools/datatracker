#!/bin/bash

# A little bit of setup
export LANG=en_GB.UTF-8

WORKSPACEDIR="/usr/local/share/datatracker"

echo "Gathering info ..."
if [ ! "$USER" ]; then
    echo "Environment variable USER is not set -- will set USER='django'."
    USER="django"
fi
if [ ! "$UID" ]; then
    echo "Environment variable UID is not set -- will set UID='1000'."
    UID="1000"
fi
if [ ! "$GID" ]; then
    echo "Environment variable GID is not set -- will set GID='1000'."
    GID="1000"
fi
if [ ! "$TAG" ]; then
    echo "Environment variable TAG is not set -- will set TAG='datatracker'."
    TAG="datatracker"
fi
echo "User $USER ($UID:$GID)"

echo "Checking if syslogd is running ..."
if ! /etc/init.d/rsyslog status > /dev/null; then
    echo "Starting syslogd ..."
    /etc/init.d/rsyslog start
fi

echo "Waiting for DB container to come online ..."
wget -qO- https://raw.githubusercontent.com/eficode/wait-for/v2.1.3/wait-for | sh -s -- localhost:3306 -- echo "DB ready"

echo "Checking if the IETF database exists in DB container ..."
if ! mysql --protocol tcp -h localhost -u root --password=ietf --database="ietf_utf8" --execute="SHOW TABLES;" | grep -q 'django'; then
	echo "Fetching database  ..."       
	DUMPDIR=/home/$USER/$DATADIR
	wget -N --progress=bar:force:noscroll -P $DUMPDIR http://www.ietf.org/lib/dt/sprint/ietf_utf8.sql.gz

    echo "Creating database ..."
    mysql --protocol tcp -h localhost -u root --password=ietf --database="ietf_utf8" --execute="DROP DATABASE IF EXISTS ietf_utf8;"
	mysqladmin --protocol tcp -h localhost -u root --password=ietf --default-character-set=utf8 create ietf_utf8

	echo "Setting up permissions ..."
	mysql --protocol tcp -h localhost -u root --password="ietf" ietf_utf8 <<< "GRANT ALL PRIVILEGES ON ietf_utf8.* TO 'django'@'%' IDENTIFIED BY 'RkTkDPFnKpko'; FLUSH PRIVILEGES;"

	echo "Loading database (this may take a while)..."
	gunzip < $DUMPDIR/ietf_utf8.sql.gz \
        | pv --progress --bytes --rate --eta --cursor --force --size $(gzip --list --quiet $DUMPDIR/ietf_utf8.sql.gz | awk '{ print $2 }') \
        | sed -e 's/ENGINE=MyISAM/ENGINE=InnoDB/' \
        | mysql --protocol tcp -h localhost -u django --password=RkTkDPFnKpko -s -f ietf_utf8 \
        && rm $DUMPDIR/ietf_utf8.sql.gz
fi

if ! grep -q ":$GID:$" /etc/group ; then
    echo "Creating group entry for GID '$GID' ..."
    groupadd -g "$GID" "$USER"
fi
if ! id -u "$USER" &> /dev/null; then
    echo "Creating user '$USER' ..."
    useradd -s /bin/bash --groups staff,sudo --uid $UID --gid $GID $USER
    echo "$USER:$USER" | chpasswd
fi

VIRTDIR="/opt/home/$USER/$TAG"
echo "Checking that there's a virtual environment for $TAG ..."
if [ ! -f $VIRTDIR/bin/activate ]; then
    echo "Setting up python virtualenv at $VIRTDIR ..."
    mkdir -p $VIRTDIR
    python3.6 -m venv $VIRTDIR
    echo -e "
# This is from $VIRTDIR/bin/activate, to activate the
# datatracker virtual python environment on docker container entry:
" >> /etc/bash.bashrc
    cat $VIRTDIR/bin/activate >> /etc/bash.bashrc
    cat /usr/local/share/datatracker/docker/setprompt >> /etc/bash.bashrc 
else
    echo "Using virtual environment at $VIRTDIR"
fi

echo "Activating the virtual python environment ..."
. $VIRTDIR/bin/activate

if [ ! -f "$WORKSPACEDIR/ietf/settings_local.py" ]; then
    echo "Setting up a default settings_local.py ..."
    cp $WORKSPACEDIR/.devcontainer/settings_local.py $WORKSPACEDIR/ietf/settings_local.py
fi

if [ ! -f "$WORKSPACEDIR/ietf/settings_local_debug.py" ]; then
    echo "Setting up a default settings_local_debug.py ..."
    cp $WORKSPACEDIR/.devcontainer/settings_local_debug.py $WORKSPACEDIR/ietf/settings_local_debug.py
fi

for sub in test/id/ test/staging/ test/archive/ test/rfc test/media test/wiki/ietf; do
    dir="$WORKSPACEDIR/$sub"
    if [ ! -d "$dir"  ]; then
	echo "Creating dir $dir"
	mkdir -p "$dir";
    fi
done

for sub in					\
	nomcom_keys/public_keys			\
	developers/ietf-ftp			\
	developers/ietf-ftp/bofreq		\
	developers/ietf-ftp/charter		\
	developers/ietf-ftp/conflict-reviews	\
	developers/ietf-ftp/internet-drafts	\
	developers/ietf-ftp/rfc			\
	developers/ietf-ftp/status-changes	\
	developers/ietf-ftp/yang/catalogmod	\
	developers/ietf-ftp/yang/draftmod	\
	developers/ietf-ftp/yang/ianamod	\
	developers/ietf-ftp/yang/invalmod	\
	developers/ietf-ftp/yang/rfcmod		\
	developers/www6s			\
	developers/www6s/staging		\
	developers/www6s/wg-descriptions	\
	developers/www6s/proceedings		\
	developers/www6/			\
	developers/www6/iesg			\
	developers/www6/iesg/evaluation		\
	; do
    dir="$WORKSPACEDIR/data/$sub"
    if [ ! -d "$dir"  ]; then
	echo "Creating dir $dir"
	mkdir -p "$dir";
	chown "$USER" "$dir"
    fi
done

if [ ! -f "$WORKSPACEDIR/test/data/draft-aliases" ]; then
    echo "Generating draft aliases ..."
    ietf/bin/generate-draft-aliases }
fi

if [ ! -f "$WORKSPACEDIR/test/data/group-aliases" ]; then
    echo "Generating group aliases ..."
    ietf/bin/generate-wg-aliases }
fi

chown -R $USER /opt/home/$USER
chmod -R g+w   /usr/local/lib/		# so we can patch libs if needed

cd "$WORKSPACEDIR" || cd "/home/$USER/"

if ! echo "$LANG" | grep "UTF-8"; then
    echo ""
    echo "Make sure you export LANG=en_GB.UTF-8 (or another UTF-8 locale) in your .bashrc"
else
    echo "LANG=$LANG"
fi

HOME=/opt/home/$USER

/usr/local/bin/python $WORKSPACEDIR/ietf/manage.py check --settings=settings_local

echo "Done!"

# su -p $USER

exec "$@"