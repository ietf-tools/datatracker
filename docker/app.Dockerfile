# See here for image contents: https://github.com/microsoft/vscode-dev-containers/tree/v0.202.5/containers/python-3/.devcontainer/base.Dockerfile

# [Choice] Python version (use -bullseye variants on local arm64/Apple Silicon): 3, 3.10, 3.9, 3.8, 3.7, 3.6, 3-bullseye, 3.10-bullseye, 3.9-bullseye, 3.8-bullseye, 3.7-bullseye, 3.6-bullseye, 3-buster, 3.10-buster, 3.9-buster, 3.8-buster, 3.7-buster, 3.6-buster
ARG VARIANT="3.10-bullseye"
FROM mcr.microsoft.com/vscode/devcontainers/python:0-${VARIANT}
LABEL maintainer="IETF Tools Team <tools-discuss@ietf.org>"

# [Choice] Node.js version: none, lts/*, 16, 14, 12, 10
ARG NODE_VERSION="none"
RUN if [ "${NODE_VERSION}" != "none" ]; then su vscode -c "umask 0002 && . /usr/local/share/nvm/nvm.sh && nvm install ${NODE_VERSION} 2>&1"; fi

EXPOSE 8000

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update

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
	enscript \
	fish \
	gawk \
	gcc \
	git \
	gnupg \
	graphviz \
	jq \
	less \
	libmagic-dev \
	libmariadb-dev \
	locales \
	mariadb-client \
    netcat \
	nano \
	pigz \
	pv \
	python3-ipython \
	ripgrep \
	rsync \
	rsyslog \
	subversion \
	unzip \
	wget \
    yang-tools && \
	zsh

# Install chromedriver
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list && \
    apt-get update -y && \
    apt-get install -y google-chrome-stable && \
    CHROMEVER=$(google-chrome --product-version | grep -o "[^\.]*\.[^\.]*\.[^\.]*") && \
    DRIVERVER=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROMEVER") && \
    wget -q --continue -P /chromedriver "http://chromedriver.storage.googleapis.com/$DRIVERVER/chromedriver_linux64.zip" && \
    unzip /chromedriver/chromedriver* -d /chromedriver && \
    ln -s /chromedriver/chromedriver /usr/local/bin/chromedriver && \
    ln -s /chromedriver/chromedriver /usr/bin/chromedriver

# Get rid of installation files we don't need in the image, to reduce size
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# Set locale to en_US.UTF-8
RUN echo "LC_ALL=en_US.UTF-8" >> /etc/environment && \
    echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen && \
    echo "LANG=en_US.UTF-8" > /etc/locale.conf && \
    dpkg-reconfigure locales && \
    locale-gen en_US.UTF-8 && \
    update-locale LC_ALL en_US.UTF-8
ENV LC_ALL en_US.UTF-8

# Install bower
RUN npm install -g bower

# Install idnits
ADD https://raw.githubusercontent.com/ietf-tools/idnits-mirror/main/idnits /usr/local/bin/
RUN chmod +rx /usr/local/bin/idnits

# Install current datatracker python dependencies
COPY requirements.txt /tmp/pip-tmp/
RUN pip3 --disable-pip-version-check --no-cache-dir install -r /tmp/pip-tmp/requirements.txt \
    && rm -rf /tmp/pip-tmp

# Turn off rsyslog kernel logging (doesn't work in Docker)
RUN sed -i '/imklog/s/^/#/' /etc/rsyslog.conf

# Colorize the bash shell
RUN sed -i 's/#force_color_prompt=/force_color_prompt=/' /root/.bashrc

# Copy the startup file
COPY docker/scripts/app-init.sh /docker-init.sh
RUN sed -i 's/\r$//' /docker-init.sh && \
    chmod +x /docker-init.sh

WORKDIR /root/src
# ENTRYPOINT [ "/docker-init.sh" ]
