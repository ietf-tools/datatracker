FROM ghcr.io/ietf-tools/datatracker-app-base:latest
LABEL maintainer="IETF Tools Team <tools-discuss@ietf.org>"

ENV DEBIAN_FRONTEND=noninteractive

# Setup nginx
RUN apt-get update -y && apt-get install -y nginx
COPY docker/configs/nginx-proxy.conf /etc/nginx/sites-available/default
COPY docker/configs/nginx-502.html /var/www/html/502.html

# Copy the startup file
COPY docker/scripts/app-init.sh /docker-init.sh
COPY docker/scripts/app-start.sh /docker-start.sh
RUN sed -i 's/\r$//' /docker-init.sh && chmod +rx /docker-init.sh
RUN sed -i 's/\r$//' /docker-start.sh && chmod +rx /docker-start.sh

COPY requirements.txt /tmp/pip-tmp/
RUN pip3 --disable-pip-version-check --no-cache-dir install --user --no-warn-script-location -r /tmp/pip-tmp/requirements.txt
RUN pip3 --disable-pip-version-check --no-cache-dir install --user --no-warn-script-location pylint pylint-common pylint-django
RUN rm -rf /tmp/pip-tmp

VOLUME [ "/assets" ]
