#!/bin/bash
#
# Environment config:
#
#  CONTAINER_ROLE - datatracker, celery, or beat (defaults to datatracker)
#
case "${CONTAINER_ROLE:-datatracker}" in
    datatracker)
        exec ./datatracker-start.sh
        ;;
    celery)
        exec ./celery-start.sh --app=ietf worker
        ;;
    beat)
        exec ./celery-start.sh --app=ietf beat
        ;;
    *)
        echo "Unknown role '${CONTAINER_ROLE}'"
        exit 255       
esac
