#!/bin/bash

WORKSPACEDIR="/workspace"

cd "$WORKSPACEDIR" || exit 255

if [[ -n "${UPDATE_REQUIREMENTS}" && -r requirements.txt ]]; then
  echo "Updating requirements..."
  pip install --upgrade -r requirements.txt
fi

celery_pid=0
cleanup () {
  # Cleanly terminate the celery app by sending it a TERM, then waiting for it to exit.
  if [[ "${celery_pid}" != 0 ]]; then
    echo "Gracefully terminating celery worker. This may take a few minutes if tasks are in progress..."
    kill -TERM "${celery_pid}"
    wait "${celery_pid}"
  fi
}

trap cleanup TERM
# start celery in the background so we can trap the TERM signal
celery --app="${CELERY_APP:-ietf}" worker "$@" &
celery_pid=$!
wait "${celery_pid}"
