FROM ghcr.io/ietf-tools/datatracker-app-base:latest
LABEL maintainer="IETF Tools Team <tools-discuss@ietf.org>"

ENV DEBIAN_FRONTEND=noninteractive

# Copy the startup file
COPY docker/scripts/app-init-celery.sh /docker-init.sh
RUN sed -i 's/\r$//' /docker-init.sh && \
    chmod +x /docker-init.sh

ENTRYPOINT [ "/docker-init.sh" ]

# Install current datatracker python dependencies
COPY requirements.txt /tmp/pip-tmp/
RUN pip3 --disable-pip-version-check --no-cache-dir install --user --no-warn-script-location -r /tmp/pip-tmp/requirements.txt
RUN pip3 --disable-pip-version-check --no-cache-dir install --user --no-warn-script-location watchdog[watchmedo]
RUN rm -rf /tmp/pip-tm

VOLUME [ "/assets" ]

