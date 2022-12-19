export DEBIAN_FRONTEND=noninteractive

echo "Fixing permissions..."
chmod -R 777 ./

echo "Ensure all requirements.txt packages are installed..."
pip --disable-pip-version-check --no-cache-dir install -r requirements.txt

echo "Creating data directories..."
chmod +x ./docker/scripts/app-create-dirs.sh
./docker/scripts/app-create-dirs.sh

# Add Postgresql Apt Repository to get 14    
echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" | tee /etc/apt/sources.list.d/pgdg.list
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add -

# Install pg client and pgloader
apt-get update
apt-get install -y --no-install-recommends postgresql-client-14 pgloader
    
# Wait for DB containers
echo "Waiting for DB containers to come online..."
/usr/local/bin/wait-for db:3306 -- echo "MariaDB ready"
/usr/local/bin/wait-for pgdb:5432 -- echo "PostgreSQL ready"

# Alter search path
psql -U django -h pgdb -d ietf -v ON_ERROR_STOP=1 -c '\x' -c 'ALTER USER django set search_path=ietf_utf8,django,public;'

# Copy settings files
cp ./docker/configs/settings_local.py ./ietf/settings_local.py
cp ./docker/configs/settings_mysqldb.py ./ietf/settings_mysqldb.py
cp ./docker/configs/settings_postgresqldb.py ./ietf/settings_postgresqldb.py

# Switch to MySQL config
cat ./ietf/settings_local.py | sed 's/from ietf.settings_postgresqldb import DATABASES/from ietf.settings_mysqldb import DATABASES/' > /tmp/settings_local.py && mv /tmp/settings_local.py ./ietf/settings_local.py

# Initial checks
echo "Running initial checks..."
/usr/local/bin/python ./ietf/manage.py check --settings=settings_local

# The mysql database is always freshly build container from the 
# image build of last-night's dump when this script is run
# The first run of migrations will run anything merged from main that
# that hasn't been released, and the few pre-engine-shift migrations
# that the feat/postgres branch adds. It is guaranteed to fail at
# utils.migrations.0004_pause_to_change_database_engines (where it
# fails on purpose, hence the `|| true` so we may proceed
/usr/local/bin/python ./ietf/manage.py migrate --settings=settings_local || true

# Switch to PostgreSQL config
cat ./ietf/settings_local.py | sed 's/from ietf.settings_mysqldb import DATABASES/from ietf.settings_postgresqldb import DATABASES/' > /tmp/settings_local.py && mv /tmp/settings_local.py ./ietf/settings_local.py

# Now transfer the migrated database from mysql to postgres unless that's already happened.
echo "Transferring migrated database from MySQL to PostgreSQL..."
EMPTY_CHECK=`psql -U django -h pgdb -d ietf -c "\dt" 2>&1`
if echo ${EMPTY_CHECK} | grep -q "Did not find any relations."; then
    cat << EOF > cast.load
LOAD DATABASE
FROM mysql://django:RkTkDPFnKpko@db/ietf_utf8
INTO postgresql://django:RkTkDPFnKpko@pgdb/ietf
WITH workers = 3, concurrency = 1, batch size = 1MB, batch rows = 1000
CAST type varchar to text drop typemod;
EOF
    pgloader --verbose --logfile=ietf_pgloader.run --summary=ietf_pgloader.summary cast.load
    rm cast.load
    /usr/local/bin/python ./ietf/manage.py migrate --settings=settings_local
else
    echo "The postgres database is in an unexpected state"
    echo ${EMPTY_CHECK}
fi

# Create export dump
echo "Creating export dump..."
pg_dump -h pgdb -U django -F c ietf > ietf.dump

echo "Done."
