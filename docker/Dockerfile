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

FROM debian:wheezy
MAINTAINER Henrik Levkowetz <henrik@levkowetz.com>

# Use backports
RUN echo "deb http://http.debian.net/debian wheezy-backports main contrib non-free" >> /etc/apt/sources.list

# Run apt-get noninteractive
ENV DEBIAN_FRONTEND=noninteractive

# Some basic packages we'll need
RUN apt-get update && apt-get install -qy apt-utils wget less python procps ca-certificates awk

# MySQL
RUN apt-get update && apt-get install -qy mysql-server

# Subversion
RUN apt-get update && apt-get install -qy subversion/wheezy-backports libsvn1/wheezy-backports

# Some packages needed to compile requirements
RUN apt-get update && apt-get install -qy libmysqlclient-dev python-dev libxml2-dev libxslt-dev

# Pip
ENV PYTHONWARNINGS="ignore:a true SSLContext object"
WORKDIR /usr/src
RUN wget -q https://bootstrap.pypa.io/get-pip.py
RUN python get-pip.py
RUN pip --version
RUN pip install virtualenv

# idnits and dependencies
RUN wget -q -P /usr/local/bin/ https://tools.ietf.org/tools/idnits/idnits
RUN chmod +x /usr/local/bin/idnits

# A default user
RUN useradd -ms /bin/bash django
USER django
WORKDIR /home/django

# Check out trunk, in order to verify setup by running tests
RUN mkdir -p ~/src
WORKDIR /home/django/src
RUN svn co https://svn.tools.ietf.org/svn/tools/ietfdb/trunk trunk

# Set up a virtualenv, install requirements, run tests
WORKDIR /home/django/src/trunk
RUN virtualenv .
RUN . bin/activate; pip install -r requirements.txt
COPY settings_local.py ./settings_local.py
RUN . bin/activate; ietf/manage.py test --settings=settings_sqlitetest

WORKDIR /home
