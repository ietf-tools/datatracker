# See here for image contents: https://github.com/microsoft/vscode-dev-containers/tree/v0.202.5/containers/python-3/.devcontainer/base.Dockerfile

# [Choice] Python version (use -bullseye variants on local arm64/Apple Silicon): 3, 3.10, 3.9, 3.8, 3.7, 3.6, 3-bullseye, 3.10-bullseye, 3.9-bullseye, 3.8-bullseye, 3.7-bullseye, 3.6-bullseye, 3-buster, 3.10-buster, 3.9-buster, 3.8-buster, 3.7-buster, 3.6-buster
ARG VARIANT="3.10-bullseye"
FROM mcr.microsoft.com/vscode/devcontainers/python:0-${VARIANT}
LABEL maintainer="IETF Tools Team <tools-discuss@ietf.org>"

# [Choice] Node.js version: none, lts/*, 16, 14, 12, 10
ARG NODE_VERSION="none"
RUN if [ "${NODE_VERSION}" != "none" ]; then su vscode -c "umask 0002 && . /usr/local/share/nvm/nvm.sh && nvm install ${NODE_VERSION} 2>&1"; fi
RUN npm install -g yarn

EXPOSE 8000

ENV DEBIAN_FRONTEND=noninteractive

# Add Docker Source
RUN curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
RUN echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian \
    $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

RUN apt-get update --fix-missing

# apt-get upgrade is normally not a good idea, but this is a dev container
RUN apt-get -qy upgrade

# Install the packages we need
RUN apt-get install -qy \
	apache2-utils \
	apt-file \
	apt-utils \
	bash \
	build-essential \
	curl \
    default-jdk \
    docker-ce-cli \
	enscript \
	fish \
	gawk \
	gcc \
	ghostscript \
	git \
	gnupg \
	graphviz \
	jq \
	less \
    libcairo2-dev \
    libgtk2.0-0 \
    libgtk-3-0 \
    libnotify-dev \
    libgconf-2-4 \
    libgbm-dev \
    libnss3 \
    libxss1 \
    libasound2 \
    libxtst6 \
	libmagic-dev \
	libmariadb-dev \
    libmemcached-tools \
	locales \
	mariadb-client \
    memcached \
    netcat \
	nano \
	pigz \
	pv \
	python3-ipython \
	ripgrep \
	rsync \
	rsyslog \
    ruby \
    ruby-rubygems \
	subversion \
	unzip \
	wget \
    xauth \
    xvfb \
    yang-tools \
	zsh

# Install kramdown-rfc2629 (ruby)
RUN gem install kramdown-rfc2629

# Install chromedriver if supported
COPY docker/scripts/app-install-chromedriver.sh /tmp/app-install-chromedriver.sh
RUN sed -i 's/\r$//' /tmp/app-install-chromedriver.sh && \
    chmod +x /tmp/app-install-chromedriver.sh
RUN /tmp/app-install-chromedriver.sh

# Get rid of installation files we don't need in the image, to reduce size
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# "fake" dbus address to prevent errors
# https://github.com/SeleniumHQ/docker-selenium/issues/87
ENV DBUS_SESSION_BUS_ADDRESS=/dev/null

# avoid million NPM install messages
ENV npm_config_loglevel warn
# allow installing when the main user is root
ENV npm_config_unsafe_perm true
# disable NPM funding messages
ENV npm_config_fund false

# Set locale to en_US.UTF-8
RUN echo "LC_ALL=en_US.UTF-8" >> /etc/environment && \
    echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen && \
    echo "LANG=en_US.UTF-8" > /etc/locale.conf && \
    dpkg-reconfigure locales && \
    locale-gen en_US.UTF-8 && \
    update-locale LC_ALL en_US.UTF-8
ENV LC_ALL en_US.UTF-8

# Install idnits
ADD https://raw.githubusercontent.com/ietf-tools/idnits-mirror/main/idnits /usr/local/bin/
RUN chmod +rx /usr/local/bin/idnits

# Turn off rsyslog kernel logging (doesn't work in Docker)
RUN sed -i '/imklog/s/^/#/' /etc/rsyslog.conf

# Colorize the bash shell
RUN sed -i 's/#force_color_prompt=/force_color_prompt=/' /root/.bashrc

ADD https://raw.githubusercontent.com/eficode/wait-for/v2.1.3/wait-for /usr/local/bin/
RUN chmod +rx /usr/local/bin/wait-for

# Copy the startup file
COPY docker/scripts/app-init.sh /docker-init.sh
RUN sed -i 's/\r$//' /docker-init.sh && \
    chmod +x /docker-init.sh

# Create workspace
RUN mkdir -p /workspace
WORKDIR /workspace

USER vscode:vscode

# Install current datatracker python dependencies
COPY requirements.txt /tmp/pip-tmp/
RUN pip3 --disable-pip-version-check --no-cache-dir install --user -r /tmp/pip-tmp/requirements.txt
RUN sudo rm -rf /tmp/pip-tmp

# ENTRYPOINT [ "/docker-init.sh" ]
