# Dockerfile for celery worker
#
FROM ghcr.io/ietf-tools/datatracker-app-base:latest
LABEL maintainer="IETF Tools Team <tools-discuss@ietf.org>"

ENV DEBIAN_FRONTEND=noninteractive

# Install endpoint script
COPY dev/celery/docker-init.sh /docker-init.sh
RUN chmod +rx /docker-init.sh

ENTRYPOINT [ "/docker-init.sh" ]