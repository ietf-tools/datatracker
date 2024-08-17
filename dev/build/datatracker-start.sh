#!/bin/bash -e

echo "Running Datatracker checks..."
./ietf/manage.py check

if ! ietf/manage.py migrate --check ; then
    echo "Unapplied migrations found, waiting to start..."
    sleep 5
    while ! ietf/manage.py migrate --check ; do 
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
gunicorn \
          -c /workspace/gunicorn.conf.py \
          --workers "${DATATRACKER_GUNICORN_WORKERS:-9}" \
          --max-requests "${DATATRACKER_GUNICORN_MAX_REQUESTS:-32768}" \
          --timeout "${DATATRACKER_GUNICORN_TIMEOUT:-180}" \
          --bind :8000 \
          --log-level "${DATATRACKER_GUNICORN_LOG_LEVEL:-info}" \
          --capture-output \
          --access-logfile -\
          ${DATATRACKER_GUNICORN_EXTRA_ARGS} \
          ietf.wsgi:application &
gunicorn_pid=$!
wait "${gunicorn_pid}"
