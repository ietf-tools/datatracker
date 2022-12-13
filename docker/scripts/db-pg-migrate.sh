export DEBIAN_FRONTEND=noninteractive

chmod +x ./dev/tests/prepare.sh
sh ./dev/tests/prepare.sh

mkdir -p pgdata

# Setup pg database container
echo "Setting up PostgreSQL DB container..."
docker run -d --name pgdb -p 5432:5432 \
    -e POSTGRES_PASSWORD=RkTkDPFnKpko \
    -e POSTGRES_USER=django \
    -e POSTGRES_DB=ietf \
    -e POSTGRES_HOST_AUTH_METHOD=trust \
    -v ./pgdata:/var/lib/postgresql/data
    postgres:14.5

# Add Postgresql Apt Repository to get 14    
echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" | tee /etc/apt/sources.list.d/pgdg.list
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add -

# Install pg client and pgloader
apt-get update
apt-get install -y --no-install-recommends postgresql-client-14 pgloader

# Copy settings files
cp ./docker/configs/settings_local.py ./ietf/settings_local.py
cp ./docker/configs/settings_mysqldb.py ./ietf/settings_mysqldb.py
cp ./docker/configs/settings_postgresqldb.py ./ietf/settings_postgresqldb.py

# Wait for DB containers
echo "Waiting for DB containers to come online..."
/usr/local/bin/wait-for db:3306 -- echo "MariaDB ready"
/usr/local/bin/wait-for pgdb:5432 -- echo "Postgresql ready"

# Initial checks
echo "Running initial checks..."
/usr/local/bin/python ./ietf/manage.py check --settings=settings_local

# Migrate, adjusting to what the current state of the underlying database might be:
/usr/local/bin/python ./ietf/manage.py migrate --settings=settings_local

# We may be starting with a post 9.0.0 deploy dump, so run the migrations again before switching engines to catch any pre-postgres migrations that may be merged in from main post 9.0.0 (and any that are specific to feat/postgres that need to run before we switch engines)
/usr/local/bin/python ./ietf/manage.py migrate --settings=settings_local || true

cat ./ietf/settings_local.py | sed 's/from ietf.settings_mysqldb import DATABASES/from ietf.settings_postgresqldb import DATABASES/' > /tmp/settings_local.py && mv /tmp/settings_local.py ./ietf/settings_local.py

# Now transfer the migrated database from mysql to postgres unless that's already happened.
echo "Transferring migrated database from MySQL to PostgreSQL..."
if psql -U django -h pgdb -d ietf -c "\dt" 2>&1 | grep -q "Did not find any relations."; then
    cat << EOF > cast.load
LOAD DATABASE
FROM mysql://django:RkTkDPFnKpko@db/ietf_utf8
INTO postgresql://django:RkTkDPFnKpko@pgdb/ietf
CAST type varchar to text drop typemod;
EOF
    time pgloader --verbose --logfile=ietf_pgloader.run --summary=ietf_pgloader.summary cast.load
    rm cast.load
    /usr/local/bin/python ./ietf/manage.py migrate --settings=settings_local
fi

# Stop postgreSQL container
echo "Stopping PostgreSQL container..."
docker stop pgdb

echo "Done."
