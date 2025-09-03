FROM ghcr.io/ietf-tools/datatracker-app-base:latest
LABEL maintainer="IETF Tools Team <tools-discuss@ietf.org>"

ENV DEBIAN_FRONTEND=noninteractive

# Install needed packages and setup non-root user.
ARG USERNAME=dev
ARG USER_UID=1000
ARG USER_GID=$USER_UID
COPY docker/scripts/app-setup-debian.sh /tmp/library-scripts/docker-setup-debian.sh
RUN sed -i 's/\r$//' /tmp/library-scripts/docker-setup-debian.sh && chmod +x /tmp/library-scripts/docker-setup-debian.sh

# Add Postgresql Apt Repository to get 14    
RUN echo "deb http://apt.postgresql.org/pub/repos/apt $(. /etc/os-release && echo "$VERSION_CODENAME")-pgdg main" | tee /etc/apt/sources.list.d/pgdg.list
RUN wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add -

RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get install -y --no-install-recommends postgresql-client-14 pgloader \
    # Remove imagemagick due to https://security-tracker.debian.org/tracker/CVE-2019-10131
    && apt-get purge -y imagemagick imagemagick-6-common \
    # Install common packages, non-root user
    # Syntax: ./docker-setup-debian.sh [install zsh flag] [username] [user UID] [user GID] [upgrade packages flag] [install Oh My Zsh! flag] [Add non-free packages]
    && bash /tmp/library-scripts/docker-setup-debian.sh "true" "${USERNAME}" "${USER_UID}" "${USER_GID}" "false" "true" "true"

# Setup default python tools in a venv via pipx to avoid conflicts
ENV PIPX_HOME=/usr/local/py-utils \
    PIPX_BIN_DIR=/usr/local/py-utils/bin
ENV PATH=${PATH}:${PIPX_BIN_DIR}
COPY docker/scripts/app-setup-python.sh /tmp/library-scripts/docker-setup-python.sh
RUN sed -i 's/\r$//' /tmp/library-scripts/docker-setup-python.sh && chmod +x /tmp/library-scripts/docker-setup-python.sh
RUN bash /tmp/library-scripts/docker-setup-python.sh "none" "/usr/local" "${PIPX_HOME}" "${USERNAME}"

# Setup nginx
COPY docker/scripts/app-setup-nginx.sh /tmp/library-scripts/docker-setup-nginx.sh
RUN sed -i 's/\r$//' /tmp/library-scripts/docker-setup-nginx.sh && chmod +x /tmp/library-scripts/docker-setup-nginx.sh
RUN bash /tmp/library-scripts/docker-setup-nginx.sh
COPY docker/configs/nginx-proxy.conf /etc/nginx/sites-available/default
COPY docker/configs/nginx-502.html /var/www/html/502.html

# Remove library scripts for final image
RUN rm -rf /tmp/library-scripts

# Copy the startup file
COPY docker/scripts/app-init.sh /docker-init.sh
COPY docker/scripts/app-start.sh /docker-start.sh
RUN sed -i 's/\r$//' /docker-init.sh && chmod +rx /docker-init.sh
RUN sed -i 's/\r$//' /docker-start.sh && chmod +rx /docker-start.sh

# Fix user UID / GID to match host
RUN groupmod --gid $USER_GID $USERNAME \
    && usermod --uid $USER_UID --gid $USER_GID $USERNAME \
    && chown -R $USER_UID:$USER_GID /home/$USERNAME \
    || exit 0

# Switch to local dev user
USER dev:dev

# Install current datatracker python dependencies
COPY requirements.txt /tmp/pip-tmp/
RUN pip3 --disable-pip-version-check --no-cache-dir install --user --no-warn-script-location -r /tmp/pip-tmp/requirements.txt
RUN pip3 --disable-pip-version-check --no-cache-dir install --user --no-warn-script-location pylint pylint-common pylint-django
RUN sudo rm -rf /tmp/pip-tmp

VOLUME [ "/assets" ]
