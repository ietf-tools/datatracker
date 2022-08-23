#!/bin/bash -e
#
# Environment parameters:
#
#   CELERY_APP - name of application to pass to celery (defaults to ietf)
#
#   CELERY_ROLE - 'worker' or 'beat' (defaults to 'worker')
#
#   CELERY_UID - numeric uid for the celery worker process
#
#   CELERY_GID - numeric gid for the celery worker process
#
#   UPDATES_REQUIREMENTS_FROM - path, relative to /workspace mount, to a pip requirements
#       file that should be installed at container startup. Default is no package install/update.
#
#   DEBUG_TERM_TIMING - if non-empty, writes debug messages during shutdown after a TERM signal
#
WORKSPACEDIR="/workspace"
CELERY_ROLE="${CELERY_ROLE:-worker}"

cd "$WORKSPACEDIR" || exit 255

if [[ -n "${UPDATE_REQUIREMENTS_FROM}" ]]; then
  reqs_file="${WORKSPACEDIR}/${UPDATE_REQUIREMENTS_FROM}"
  echo "Updating requirements from ${reqs_file}..."
  pip install --upgrade -r "${reqs_file}"
fi

if [[ "${CELERY_ROLE}" == "worker" ]]; then
    echo "Running initial checks..."
    /usr/local/bin/python $WORKSPACEDIR/ietf/manage.py check
fi

CELERY_OPTS=( "${CELERY_ROLE}" )
if [[ -n "${CELERY_UID}" ]]; then
  # ensure that some group with the necessary GID exists in container
  if ! id "${CELERY_UID}" ; then
    adduser --system --uid "${CELERY_UID}" --no-create-home --disabled-login "celery-user-${CELERY_UID}"
  fi
  CELERY_OPTS+=("--uid=${CELERY_UID}")
fi

if [[ -n "${CELERY_GID}" ]]; then
  # ensure that some group with the necessary GID exists in container
  if ! getent group "${CELERY_GID}" ; then
    addgroup --gid "${CELERY_GID}" "celery-group-${CELERY_GID}"
  fi
  CELERY_OPTS+=("--gid=${CELERY_GID}")
fi

log_term_timing_msgs () {
  # output periodic debug message
  while true; do
    echo "Waiting for celery worker shutdown ($(date --utc --iso-8601=ns))"
    sleep 0.5s
  done
}

cleanup () {
  # Cleanly terminate the celery app by sending it a TERM, then waiting for it to exit.
  if [[ -n "${celery_pid}" ]]; then
    echo "Gracefully terminating celery worker. This may take a few minutes if tasks are in progress..."
    kill -TERM "${celery_pid}"
    if [[ -n "${DEBUG_TERM_TIMING}" ]]; then
      log_term_timing_msgs &
    fi
    wait "${celery_pid}"
  fi
}

trap 'trap "" TERM; cleanup' TERM
# start celery in the background so we can trap the TERM signal
celery --app="${CELERY_APP:-ietf}" "${CELERY_OPTS[@]}" "$@" &
celery_pid=$!
wait "${celery_pid}"
