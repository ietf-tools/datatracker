FROM ghcr.io/ietf-tools/datatracker-app-base:latest
LABEL maintainer="IETF Tools Team <tools-discuss@ietf.org>"

ENV DEBIAN_FRONTEND=noninteractive

# Install PostgreSQL Client tools
RUN /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y && \
	apt-get update --fix-missing && apt-get install -qy --no-install-recommends postgresql-client-17

# Setup nginx
COPY docker/configs/nginx-proxy.conf /etc/nginx/sites-available/default
COPY docker/configs/nginx-502.html /var/www/html/502.html

# Copy the startup file
COPY docker/scripts/app-init.sh /docker-init.sh
COPY docker/scripts/app-start.sh /docker-start.sh
RUN sed -i 's/\r$//' /docker-init.sh && chmod +rx /docker-init.sh
RUN sed -i 's/\r$//' /docker-start.sh && chmod +rx /docker-start.sh

# Setup non-root user
RUN apt-get update --fix-missing && apt-get install -qy --no-install-recommends sudo
RUN groupadd -g 1000 dev && \
    useradd -c "Dev Datatracker User" -u 1000 -g dev -m -s /bin/false dev && \
    adduser dev sudo && \
    echo "dev ALL=(ALL:ALL) NOPASSWD: ALL" | tee /etc/sudoers.d/dev

# Switch to local dev user
USER dev:dev

# Install current datatracker python dependencies
COPY requirements.txt /tmp/pip-tmp/
RUN pip3 --disable-pip-version-check --no-cache-dir install --user --no-warn-script-location -r /tmp/pip-tmp/requirements.txt
RUN pip3 --disable-pip-version-check --no-cache-dir install --user --no-warn-script-location pylint pylint-common pylint-django
RUN sudo rm -rf /tmp/pip-tmp

VOLUME [ "/assets" ]
