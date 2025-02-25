#!/bin/bash
#
# Environment config:
#
#  CONTAINER_ROLE - datatracker, celery, beat, or flower (defaults to datatracker)
#
case "${CONTAINER_ROLE:-datatracker}" in
    auth)
        exec ./datatracker-start.sh
        ;;
    beat)
        exec ./celery-start.sh --app=ietf beat
        ;;
    celery)
        exec ./celery-start.sh --app=ietf worker
        ;;
    datatracker)
        exec ./datatracker-start.sh
        ;;
    flower)
        exec ./celery-start.sh --app=ietf flower
        ;;
    migrations)
        exec ./migration-start.sh
        ;;
    *)
        echo "Unknown role '${CONTAINER_ROLE}'"
        exit 255       
esac
