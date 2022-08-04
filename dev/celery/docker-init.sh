#!/bin/bash
#
# Environment parameters:
#
#   CELERY_APP - name of application to pass to celery (defaults to ietf)
#
#   UPDATES_REQUIREMENTS_FROM - path, relative to /workspace mount, to a pip requirements
#       file that should be installed at container startup. Default is no package install/update.
#
WORKSPACEDIR="/workspace"

cd "$WORKSPACEDIR" || exit 255

if [[ -n "${UPDATE_REQUIREMENTS_FROM}" ]]; then
  reqs_file="${WORKSPACEDIR}/${UPDATE_REQUIREMENTS_FROM}"
  echo "Updating requirements from ${reqs_file}..."
  pip install --upgrade -r "${reqs_file}"
fi

echo "Running initial checks..."
/usr/local/bin/python $WORKSPACEDIR/ietf/manage.py check

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
celery --app="${CELERY_APP:-ietf}" --uid="${CELERY_UID:-0}" --gid="${CELERY_GID:-0}" worker "$@" &
celery_pid=$!
wait "${celery_pid}"
