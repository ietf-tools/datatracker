#!/bin/bash -e

echo "Running Datatracker checks..."
./ietf/manage.py check

# Check whether the blobdb database exists - inspectdb will return a false
# status if not.
if ietf/manage.py inspectdb --database blobdb > /dev/null 2>&1; then
    HAVE_BLOBDB="yes"
fi

migrations_applied_for () {
    local DATABASE=${1:-default}
    ietf/manage.py migrate --check --database "$DATABASE"
}

migrations_all_applied () {
    if [[ "$HAVE_BLOBDB" == "yes" ]]; then
        migrations_applied_for default && migrations_applied_for blobdb
    else
        migrations_applied_for default
    fi
}

if ! migrations_all_applied; then
    echo "Unapplied migrations found, waiting to start..."
    sleep 5
    while ! migrations_all_applied ; do 
        echo "... still waiting for migrations..."
        sleep 5
    done
fi

echo "Starting Datatracker..."

# trap TERM and shut down gunicorn
cleanup () {
    if [[ -n "${gunicorn_pid}" ]]; then
        echo "Terminating gunicorn..."
        kill -TERM "${gunicorn_pid}"
        wait "${gunicorn_pid}"
    fi
}

trap 'trap "" TERM; cleanup' TERM

# start gunicorn in the background so we can trap the TERM signal
gunicorn -c /workspace/gunicorn.conf.py ${DATATRACKER_GUNICORN_EXTRA_ARGS} ietf.wsgi:application &
gunicorn_pid=$!
wait "${gunicorn_pid}"
