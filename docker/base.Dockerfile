FROM python:3.9-bullseye
LABEL maintainer="IETF Tools Team <tools-discuss@ietf.org>"

ENV DEBIAN_FRONTEND=noninteractive
ENV NODE_MAJOR=16

# Update system packages
RUN apt-get update \
    && apt-get -qy upgrade \
    && apt-get -y install --no-install-recommends apt-utils dialog 2>&1

# Add Node.js Source
RUN apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && mkdir -p /etc/apt/keyrings\
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg
RUN echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_$NODE_MAJOR.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list

# Add Docker Source
RUN curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
RUN echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Add PostgreSQL Source 
RUN echo "deb http://apt.postgresql.org/pub/repos/apt $(. /etc/os-release && echo "$VERSION_CODENAME")-pgdg main" | tee /etc/apt/sources.list.d/pgdg.list
RUN wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add -

# Install the packages we need
RUN apt-get update --fix-missing && apt-get install -qy --no-install-recommends \
	apache2-utils \
	apt-file \
	bash \
	build-essential \
	curl \
	default-jdk \
	docker-ce-cli \
	enscript \
	firefox-esr \
	gawk \
	g++ \
	gcc \
	ghostscript \
	git \
	gnupg \
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
	make \
	mariadb-client \
	memcached \
	nano \
	netcat \
	nodejs \
	pgloader \
	pigz \
	postgresql-client-14 \
	pv \
	python3-ipython \
	ripgrep \
	rsync \
	rsyslog \
	ruby \
	ruby-rubygems \
	unzip \
	wget \
	xauth \
	xvfb \
	yang-tools \
	zsh

# Install kramdown-rfc2629 (ruby)
RUN gem install kramdown-rfc2629

# GeckoDriver
ARG GECKODRIVER_VERSION=latest
RUN GK_VERSION=$(if [ ${GECKODRIVER_VERSION:-latest} = "latest" ]; then echo "0.34.0"; else echo $GECKODRIVER_VERSION; fi) \
  && echo "Using GeckoDriver version: "$GK_VERSION \
  && wget --no-verbose -O /tmp/geckodriver.tar.gz https://github.com/mozilla/geckodriver/releases/download/v$GK_VERSION/geckodriver-v$GK_VERSION-linux64.tar.gz \
  && rm -rf /opt/geckodriver \
  && tar -C /opt -zxf /tmp/geckodriver.tar.gz \
  && rm /tmp/geckodriver.tar.gz \
  && mv /opt/geckodriver /opt/geckodriver-$GK_VERSION \
  && chmod 755 /opt/geckodriver-$GK_VERSION \
  && ln -fs /opt/geckodriver-$GK_VERSION /usr/bin/geckodriver

# Activate Yarn
RUN corepack enable

# Get rid of installation files we don't need in the image, to reduce size
RUN apt-get autoremove -y && apt-get clean -y && rm -rf /var/lib/apt/lists/* /var/cache/apt/*

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

# Install required fonts
RUN mkdir -p /tmp/fonts && \
    wget -q -O /tmp/fonts.tar.gz https://github.com/ietf-tools/xml2rfc-fonts/archive/refs/tags/3.22.0.tar.gz && \
    tar zxf /tmp/fonts.tar.gz -C /tmp/fonts && \
    mv /tmp/fonts/*/noto/* /usr/local/share/fonts/ && \
    mv /tmp/fonts/*/roboto_mono/* /usr/local/share/fonts/ && \
    rm -rf /tmp/fonts.tar.gz /tmp/fonts/ && \
    fc-cache -f

# Turn off rsyslog kernel logging (doesn't work in Docker)
RUN sed -i '/imklog/s/^/#/' /etc/rsyslog.conf

# Colorize the bash shell
RUN sed -i 's/#force_color_prompt=/force_color_prompt=/' /root/.bashrc

# Turn off rsyslog kernel logging (doesn't work in Docker)
RUN sed -i '/imklog/s/^/#/' /etc/rsyslog.conf

# Fetch wait-for utility
ADD https://raw.githubusercontent.com/eficode/wait-for/v2.1.3/wait-for /usr/local/bin/
RUN chmod +rx /usr/local/bin/wait-for

# Create assets directory
RUN mkdir -p /assets

# Create workspace
RUN mkdir -p /workspace
WORKDIR /workspace
