# This is a Dockerfile with everything in it to run the IETF datatracker.
#
# If you make changes to the datatracker that add new dependencies (python
# packages or otherwise), you need to rebuild this image to make them
# available. Do this in the top-level directory of your datatracker source
# tree:
#
# docker/build
#
# You can then execute the datatracker like this (also from the top-level
# datatracker source directory):
#
# docker/run

FROM ubuntu:hirsute
LABEL maintainer="IETF Tools Team <tools-discuss@ietf.org>"

# Default django runserver port
EXPOSE 8000

# Default mysqld/mariadb port
EXPOSE 3306

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get -y update && \
    # Install all dependencies that are available as packages
    apt-get -y install --no-install-recommends \
        apache2-utils \
        apt-file \
        apt-utils \
        chromium-driver \
        curl \
        enscript \
        gcc \
        ghostscript \
        git \
        graphviz \
        libmagic-dev \
        libmariadb-dev \
        mariadb-server \
        npm \
        pigz \
        pv \
        python-is-python3 \
        python3-dev \
        python3-pip \
        rsyslog \
        unzip \
        yang-tools && \
    # Install some other packages that are not dependencies but make life easier
    apt-get -y install --no-install-recommends \
        fish \
        less \
        nano \
        ripgrep \
        zsh && \
    apt-get -y clean && \
    rm -rf /var/lib/apt/lists/*

# Install bower
RUN npm install -g bower

# Install idnits
ADD https://tools.ietf.org/tools/idnits/idnits /usr/local/bin/
RUN chmod +rx /usr/local/bin/idnits

# Install current datatracker python dependencies
COPY requirements.txt /
RUN pip install -r /requirements.txt

# Turn off rsyslog kernel logging (doesn't work in Docker)
RUN sed -i '/imklog/s/^/#/' /etc/rsyslog.conf

# Allow access to mariadb over the network
RUN sed -i 's/127.0.0.1/0.0.0.0/' /etc/mysql/mariadb.conf.d/50-server.cnf

# Turn on mariadb performance_schema
RUN sed -i 's/\[mysqld\]/\[mysqld\]\nperformance_schema=ON/' /etc/mysql/mariadb.conf.d/50-server.cnf

# Make the mariadb sys schema available for possible installation
# We would normally use the next line, but that has a bug:
# ADD https://github.com/FromDual/mariadb-sys/archive/master.zip /
# This is the repo that has the PR:
ADD https://github.com/grooverdan/mariadb-sys/archive/refs/heads/master.zip /
RUN unzip /master.zip

# Copy the startup file
COPY docker-init.sh /docker-init.sh
RUN chmod +x /docker-init.sh

WORKDIR /root/src
ENTRYPOINT ["/docker-init.sh"]