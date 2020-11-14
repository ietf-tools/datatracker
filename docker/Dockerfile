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

FROM dyne/devuan:beowulf
LABEL maintainer="Henrik Levkowetz <henrik@levkowetz.com>"

# Default django runserver port
EXPOSE	8000

# Run apt-get noninteractive
ENV DEBIAN_FRONTEND=noninteractive
ENV DEVUAN_FRONTEND=noninteractive

# Uncomment this to be able to install and run apt-show-versions:
RUN rm -v /etc/apt/apt.conf.d/docker-compress
RUN rm -v /var/lib/apt/lists/*lz4

RUN apt-get update --allow-releaseinfo-change
RUN apt-get install -qy apt-transport-https

# Use backports, updates, and security updates
RUN echo "deb http://deb.devuan.org/merged beowulf main contrib non-free"  > /etc/apt/sources.list
RUN echo "deb http://deb.devuan.org/merged beowulf-security main contrib non-free" >> /etc/apt/sources.list
RUN echo "deb http://deb.devuan.org/merged beowulf-updates main contrib non-free" >> /etc/apt/sources.list
RUN echo "deb http://deb.devuan.org/merged beowulf-backports main contrib non-free" >> /etc/apt/sources.list

# Remove some excludes for the docker image
RUN sed -i -e '/^path-exclude=.*\/groff/d' \
           -e '/^path-exclude=.*\/locale/d' \
           -e '/^path-exclude=.*\/man/d' /etc/dpkg/dpkg.cfg.d/docker-excludes

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
	build-essential \
	bzip2 \
	ca-certificates \
	colordiff \
	gawk \
	gcc \
	ipython \
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
	libmariadbclient-dev \
	libncurses5-dev \
	libncursesw5-dev \
	libreadline-dev \
	libsqlite3-dev \
	libssl-dev \
	libsvn1 \
	libxml2-dev \
	libxslt-dev \
	libz-dev \
	libffi-dev \
	locales \
	make \
	man \
	mariadb-client \
	mariadb-server \
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

# Postgresql packages
RUN apt-get install -qy \
        postgresql-11 \
        postgresql-server-dev-11 

# Get the key used to sign the libyang repo
RUN wget -nv http://download.opensuse.org/repositories/home:liberouter/Debian_9.0/Release.key
RUN apt-key add - < Release.key
RUN rm Release.key

# Add apt source entry for libyang
RUN echo "deb http://download.opensuse.org/repositories/home:/liberouter/Debian_9.0/ /" >> /etc/apt/sources.list.d/libyang.list

# Update the package defs, and install the desired mysql from the mysql repo
RUN apt-get update
RUN apt-get install -qy libyang1

# This is expected to exist by the mysql startup scripts:
#RUN touch /etc/mysql/debian.cnf
# ------------------------------------------------------------------------------

# Get rid of installation files we don't need in the image, to reduce size
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# Enable some common locales
RUN sed -i -e 's/^. en_US/en_US/' -e 's/^. en_GB/en_GB/' -e 's/^. en_IE/en_IE/' /etc/locale.gen
RUN locale-gen

# Remove an rsyslog module that we don't need, which also requires extra permissions
RUN sed -i -e '/load="imklog"/d' /etc/rsyslog.conf

# Set up root password
RUN echo "root:root" | chpasswd

# MySQL
VOLUME /var/lib/mysql

# idnits and dependencies
ADD https://tools.ietf.org/tools/idnits/idnits /usr/local/bin/
RUN chmod +rx /usr/local/bin/idnits

# Directory for Mac certs
RUN mkdir /etc/certificates

# # Python 3
# # Comment in if OS does not provide python3.6, which is the current
# # production version
ENV PYVER=3.6.10
ENV PYREV=3.6

WORKDIR /usr/src
RUN wget -q https://www.python.org/ftp/python/$PYVER/Python-$PYVER.tar.xz
RUN tar xJf Python-$PYVER.tar.xz
RUN rm Python-$PYVER.tar.xz
WORKDIR /usr/src/Python-$PYVER/
RUN ./configure
RUN make
RUN make altinstall
WORKDIR /usr/src
RUN rm -rf /usr/src/Python-$PYVER/

ENV HOSTNAME="datatracker"

ENV DDIR="/usr/local/share/datatracker"
RUN mkdir -p $DDIR
WORKDIR $DDIR

COPY requirements.txt ./
COPY setprompt ./

COPY docker-init.sh /docker-init.sh
RUN chmod +x /docker-init.sh
ENTRYPOINT ["/docker-init.sh"]

CMD	/bin/bash
