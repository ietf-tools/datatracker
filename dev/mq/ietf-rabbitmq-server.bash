#!/bin/bash -x
#
# Environment parameters:
#
#   CELERY_PASSWORD - password for the datatracker celery user
#
export RABBITMQ_PID_FILE=/tmp/rabbitmq.pid

update_celery_password () {
  rabbitmqctl wait "${RABBITMQ_PID_FILE}" --timeout 300
  rabbitmqctl await_startup --timeout 300
  if [[ -n "${CELERY_PASSWORD}" ]]; then
    rabbitmqctl change_password datatracker <<END
${CELERY_PASSWORD}
END
  else
    rabbitmqctl clear_password datatracker
  fi
}

update_celery_password &
exec rabbitmq-server "$@"
