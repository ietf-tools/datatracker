#!/bin/bash

WORKSPACEDIR="/workspace"

cd "$WORKSPACEDIR" || exit 255

if [[ -n "${UPDATE_REQUIREMENTS}" && -r requirements.txt ]]; then
  echo "Updating requirements..."
  pip install --upgrade -r requirements.txt
fi

celery --app="${CELERY_APP:-ietf}" worker "$@"
