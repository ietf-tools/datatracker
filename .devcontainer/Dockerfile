# See here for image contents: https://github.com/microsoft/vscode-dev-containers/tree/v0.202.5/containers/python-3/.devcontainer/base.Dockerfile

# [Choice] Python version (use -bullseye variants on local arm64/Apple Silicon): 3, 3.10, 3.9, 3.8, 3.7, 3.6, 3-bullseye, 3.10-bullseye, 3.9-bullseye, 3.8-bullseye, 3.7-bullseye, 3.6-bullseye, 3-buster, 3.10-buster, 3.9-buster, 3.8-buster, 3.7-buster, 3.6-buster
ARG VARIANT="3.10-bullseye"
FROM mcr.microsoft.com/vscode/devcontainers/python:0-${VARIANT}

EXPOSE 8000

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update
RUN apt-get -qy upgrade

# Install the packages we need
RUN apt-get install -qy \
    bash \
	build-essential \
	bzip2 \
	ca-certificates \
	colordiff \
	gawk \
	gcc \
	python3-ipython \
	jq \
	less \
	libbz2-dev \
	libdb5.3-dev \
	libexpat1-dev \
	libffi-dev \
	libgdbm-dev \
	libjpeg62-turbo-dev \
	liblzma-dev \
	libmagic1 \
	libmariadb-dev-compat \
	libmariadb-dev \
	libncurses5-dev \
	libncursesw5-dev \
	libreadline-dev \
	libsqlite3-dev \
	libssl-dev \
	libsvn1 \
	libxml2-dev \
	libxslt-dev \
	libyang1 \
	libz-dev \
	libffi-dev \
	locales \
	make \
	man \
	mariadb-client \
	netcat \
	openssh-client \
	patch \
	procps \
	pv \
	rsync \
	rsyslog \
	subversion \
	sudo \
	uuid-dev  \
	vim \
	wget \
	xz-utils\
	zile \
	zlib1g-dev

# Install chromedriver
RUN apt-get update && \
    apt-get install -y gnupg wget curl unzip --no-install-recommends && \
    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - && \
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

# Enable some common locales
RUN sed -i -e 's/^. en_US/en_US/' -e 's/^. en_GB/en_GB/' -e 's/^. en_IE/en_IE/' /etc/locale.gen && \
    locale-gen

# Remove an rsyslog module that we don't need, which also requires extra permissions
RUN sed -i -e '/load="imklog"/d' /etc/rsyslog.conf

# Set up root password
RUN echo "root:root" | chpasswd

# idnits and dependencies
ADD https://tools.ietf.org/tools/idnits/idnits /usr/local/bin/
RUN chmod +rx /usr/local/bin/idnits

# Directory for Mac certs
RUN mkdir /etc/certificates

# Setup workspace
ENV HOSTNAME="datatracker"

ENV DDIR="/usr/local/share/datatracker"
RUN mkdir -p $DDIR
WORKDIR $DDIR

COPY requirements.txt /tmp/pip-tmp/
RUN pip3 --disable-pip-version-check --no-cache-dir install -r /tmp/pip-tmp/requirements.txt \
    && rm -rf /tmp/pip-tmp

COPY .devcontainer/init.sh /docker-init.sh
RUN sed -i 's/\r$//' /docker-init.sh && \
    chmod +x /docker-init.sh

# ENTRYPOINT ["/usr/local/share/datatracker/.devcontainer/init.sh"]
CMD	["sleep", "infinity"]
