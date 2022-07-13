#!/bin/bash

WORKSPACEDIR="/workspace"

cd "$WORKSPACEDIR" || exit 255

if [[ -n "${UPDATE_REQUIREMENTS}" && -r requirements.txt ]]; then
  echo "Updating requirements..."
  pip install --upgrade -r requirements.txt
fi

echo "Running initial checks..."
/usr/local/bin/python $WORKSPACEDIR/ietf/manage.py check --settings=settings_local

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
celery --app="${CELERY_APP:-ietf}" worker "$@" &
celery_pid=$!
wait "${celery_pid}"
