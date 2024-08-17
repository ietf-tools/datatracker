#!/bin/bash -e
#
# Run a celery worker
#
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

echo "Starting Celery..."

cleanup () {
  # Cleanly terminate the celery app by sending it a TERM, then waiting for it to exit.
  if [[ -n "${celery_pid}" ]]; then
    echo "Gracefully terminating celery worker. This may take a few minutes if tasks are in progress..."
    kill -TERM "${celery_pid}"
    wait "${celery_pid}"
  fi
}

trap 'trap "" TERM; cleanup' TERM

# start celery in the background so we can trap the TERM signal
celery "$@" &
celery_pid=$!
wait "${celery_pid}"
