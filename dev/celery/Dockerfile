# Dockerfile for celery worker
#
FROM python:3.9-bullseye
LABEL maintainer="IETF Tools Team <tools-discuss@ietf.org>"

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update

# Install the packages we need
RUN apt-get update --fix-missing
RUN apt-get install -qy \
    apache2-utils \
    apt-file \
    apt-utils \
    bash \
    build-essential \
    curl \
    enscript \
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
    locales \
    mariadb-client \
    netcat \
    nodejs \
    pigz \
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
    yang-tools

# Install kramdown-rfc2629 (ruby)
RUN gem install kramdown-rfc2629

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

# Install idnits
ADD https://raw.githubusercontent.com/ietf-tools/idnits-mirror/main/idnits /usr/local/bin/
RUN chmod +rx /usr/local/bin/idnits

# Install current datatracker python dependencies
COPY requirements.txt /tmp/pip-tmp/
RUN pip3 --disable-pip-version-check --no-cache-dir install -r /tmp/pip-tmp/requirements.txt \
    && rm -rf /tmp/pip-tmp

# Turn off rsyslog kernel logging (doesn't work in Docker)
RUN sed -i '/imklog/s/^/#/' /etc/rsyslog.conf

# Fetch wait-for utility
ADD https://raw.githubusercontent.com/eficode/wait-for/v2.1.3/wait-for /usr/local/bin/
RUN chmod +rx /usr/local/bin/wait-for

# Create workspace
RUN mkdir -p /workspace
WORKDIR /workspace
