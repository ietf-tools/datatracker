#!/bin/bash

echo "Gathering info ..."
MYSQLDIR="$(mysqld --verbose --help 2>/dev/null | awk '$1 == "datadir" { print $2; exit }')"

echo "Checking if MySQL base data exists ..."
if [ ! -d $MYSQLDIR/mysql ]; then
    echo "Re-installing MySQL ..."
    apt-get update && apt-get install --reinstall mysql-server
fi


echo "Checking if MySQL is running ..."
if ! /etc/init.d/mysql status; then
    echo "Starting mysql ..."
    /etc/init.d/mysql start
fi

echo "Checking if the IETF database exists at $MYSQLDIR ..."
if [ ! -d $MYSQLDIR/ietf_utf8 ]; then
    ls -l $MYSQLDIR

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

if ! id -u "$USER" &> /dev/null; then
    echo "Creating user '$USER' ..."
    useradd -ms /bin/bash $USER
fi

if [ ! -d /opt/home/$USER ]; then
    echo "Setting up python virtualenv at /opt/home/$USER ..."
    mkdir -p /opt/home/$USER
    chown $USER /opt/home/$USER
    mkdir /opt/home/$USER/datatracker
    virtualenv /opt/home/$USER/datatracker
fi

echo "Activating virtual python environment"
cat /opt/home/$USER/datatracker/bin/activate >> /etc/bash.bashrc
. /opt/home/$USER/datatracker/bin/activate


if [ ! -d /opt/home/$USER/datatracker/lib/python2.7/site-packages/django ]; then
    echo "Installing requirements (based on trunk)"
    pip install -r /home/django/src/trunk/requirements.txt
fi

if [ ! -f /opt/home/$USER/datatracker/lib/site-python/settings_local.py ]; then
    echo "Setting up a default settings_local.py"
    mkdir -p /opt/home/$USER/datatracker/lib/site-python/
    cp /home/django/src/trunk/settings_local.py /opt/home/$USER/datatracker/lib/site-python/
fi

echo "Done."

FLAG1=/opt/home/$USER/.docker-init-flag-1
if [ ! -f $FLAG1 ]; then
    touch $FLAG1
    cat <<-EOT

	******************************************************************************

	You should now cd to your svn working directory and update the datatracker
	prerequisites according to the requirements given in 'requirements.txt':

	        $ pip install -r requirements.txt

	Happy coding!

	******************************************************************************
EOT
fi

chown -R $USER /opt/home/$USER
cd /home/$USER
su $USER
