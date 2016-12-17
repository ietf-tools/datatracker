# -*- shell-mode -*-
# This file is a docker (https://www.docker.com/what-docker) recipe, which can be used to build
# a docker image which is ready to run a datatracker in development mode.
#
# It is used to build an image (once you've installed docker) using a command like this (assuming
# suitable replacement of $variables:
#
#	$ docker build -t $yourdockerid/datatracker:$version
#
# To use a pre-built image, assuming we're on OS X and have a checked-out datatracker repository
# at /Users/$login/src/6.8.1.dev0, you would start (again assuming you've installed docker)
# a container from an image, as follows:
# 
#	$ docker run -ti --name=$containername -v /Users/$login:/home/$login levkowetz/datatracker:$version /bin/bash
# 
# This maps your home directory to /home/$login in the container, and starts it running /bin/bash.
# 
# In this first version, the docker environment is set up so that tests will run successfully,
# but the database has *not* been loaded with a dump, and supporting files (drafts, charters, etc.)
# have *not* been downloaded.

FROM debian:jessie
MAINTAINER Henrik Levkowetz <henrik@levkowetz.com>

# Default django runserver port
EXPOSE	8000

# Run apt-get noninteractive
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update
RUN apt-get install -qy apt-transport-https

# Use backports, updates, and security updates; all over https
RUN echo "deb https://deb.debian.org/debian/ jessie main contrib non-free"  > /etc/apt/sources.list
RUN echo "deb https://deb.debian.org/debian/ jessie-backports main contrib non-free"  >> /etc/apt/sources.list
RUN echo "deb https://deb.debian.org/debian/ jessie-updates main contrib non-free" >> /etc/apt/sources.list

# Install needed packages
#
# We're not including graphviz and ghostscript, needed for the 3 document
# dependency graph tests; they would increase the size of the image by about
# 15%, about 100MB.

# Fetch apt package information, and upgrade to latest package versions
RUN apt-get update
RUN apt-get -qy upgrade

# Install the packages we need
RUN apt-get install -qy \
	bzip2 \
	ca-certificates \
	colordiff \
	gawk \
	gcc \
	ipython \
	less \
	libfreetype6 \
	libfontconfig \
	libjpeg62-turbo-dev \
	libsvn1 \
	libxml2-dev \
	libxslt-dev \
	libz-dev \
	locales \
	man \
	openssh-client \
	procps \
	pv \
	python \
	python-dev \
	python-m2crypto \
	python-subversion \
	realpath \
	rsync \
	subversion \
	sudo \
	vim \
	wget 

# Install SystemV init
RUN apt-get install -qy sysvinit-core \
    && cp /usr/share/sysvinit/inittab /etc/inittab

# Get rid of systemd
RUN apt-get remove --yes --purge --auto-remove systemd \
    && echo -e "\nPackage: systemd\nPin: release *\nPin-Priority: -1\n" > /etc/apt/preferences.d/no-systemd

# ------------------------------------------------------------------------------
# The following section is all about installing mysql server 5.6, instead of
# 5.5 which is provided in jessie.  It's a bit convoluted.
# ------------------------------------------------------------------------------

# Get the key used to sign the mysql repo
RUN gpg --keyserver pgp.mit.edu --recv-keys 8C718D3B5072E1F5
RUN gpg --export -a 8C718D3B5072E1F5 | apt-key add -

# Install a package which will install apt sources entries for current mysql
RUN echo 'mysql-apt-config mysql-apt-config/select-server select mysql-5.6' | debconf-set-selections
RUN echo 'mysql-apt-config mysql-apt-config/repo-url      string https://repo.mysql.com/apt/' | debconf-set-selections
RUN echo "deb https://repo.mysql.com/apt/debian/ jessie mysql-apt-config" >> /etc/apt/sources.list.d/mysql-apt-config.list
RUN apt-get update
RUN apt-get install -qy mysql-apt-config
RUN rm /etc/apt/sources.list.d/mysql-apt-config.list

# Update the package defs, and install the desired mysql from the mysql repo
RUN apt-get update
RUN apt-get install -qy mysql-community-server libmysqlclient-dev
# ------------------------------------------------------------------------------

# Get rid of installation files we don't need in the image, to reduce size
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# Enable some common locales
RUN sed -i -e 's/^. en_US/en_US/' -e 's/^. en_GB/en_GB/' -e 's/^. en_IE/en_IE/' /etc/locale.gen
RUN locale-gen

# Set up root password
RUN echo "root:root" | chpasswd

# MySQL
VOLUME /var/lib/mysql

# Pip
ENV PYTHONWARNINGS="ignore:a true SSLContext object,ignore:An HTTPS request has been made"
WORKDIR /usr/src
RUN wget -q https://bootstrap.pypa.io/get-pip.py && python get-pip.py && rm get-pip.py
RUN pip install certifi
RUN pip install virtualenv

# Phantomjs
WORKDIR /usr/local

RUN wget -qN https://tools.ietf.org/tar/phantomjs-1.9.7-linux-x86_64.tar.bz2
RUN tar xjf phantomjs-1.9.7-linux-x86_64.tar.bz2

WORKDIR /usr/local/bin
RUN ln -s /usr/local/phantomjs-1.9.7-linux-x86_64/bin/phantomjs .

# idnits and dependencies
RUN wget -q --no-check-certificate -P /usr/local/bin/ https://tools.ietf.org/tools/idnits/idnits && chmod +x /usr/local/bin/idnits

ENV DDIR="/usr/local/share/datatracker"
RUN mkdir -p $DDIR
WORKDIR $DDIR

COPY requirements.txt ./
RUN pip --no-cache-dir install -r requirements.txt

COPY settings_local.py ./
COPY setprompt ./

COPY docker-init.sh /docker-init.sh
RUN chmod +x /docker-init.sh
ENTRYPOINT ["/docker-init.sh"]

CMD	/bin/bash
