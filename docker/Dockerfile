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
    # apt-get upgrade is normally not a good idea, but this is a dev container
    apt-get upgrade && \
    # Install all dependencies that are available as packages
    apt-get -y install --no-install-recommends \
        apache2-utils \
        apt-file \
        apt-utils \
        curl \
        enscript \
        gcc \
        ghostscript \
        git \
        gnupg \
        graphviz \
        libmagic-dev \
        libmariadb-dev \
        locales \
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
    # Since snap doesn't work in Docker containers, install chromedriver per
    # https://gist.github.com/varyonic/dea40abcf3dd891d204ef235c6e8dd79#gistcomment-3160722
    curl https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list && \
    apt-get update -y && \
    apt-get install -y --no-install-recommends google-chrome-stable && \
    CHROMEVER=$(google-chrome --product-version | grep -o "[^\.]*\.[^\.]*\.[^\.]*") && \
    DRIVERVER=$(curl "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROMEVER") && \
    curl -L -O -C - "http://chromedriver.storage.googleapis.com/$DRIVERVER/chromedriver_linux64.zip" && \
    unzip chromedriver_linux64.zip -d /bin && \
    rm chromedriver_linux64.zip && \
    # Install some other packages that are not dependencies but make life easier
    apt-get -y install --no-install-recommends \
        fish \
        less \
        nano \
        ripgrep \
        subversion \
        zsh && \
    # Reduce image footprint (not that it matters given the size of the above)
    apt-get -y clean && \
    rm -rf /var/lib/apt/lists/*

# Set locale to en_US.UTF-8
RUN dpkg-reconfigure locales && \
    locale-gen en_US.UTF-8 && \
    update-locale LC_ALL en_US.UTF-8
ENV LC_ALL en_US.UTF-8

# Install bower
RUN npm install -g bower

# Install idnits
ADD https://raw.githubusercontent.com/ietf-tools/idnits-mirror/main/idnits /usr/local/bin/
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
RUN rm /master.zip

# Colorize the bash shell
RUN sed -i 's/#force_color_prompt=/force_color_prompt=/' /root/.bashrc

# Make a database dump available as part of the image, for if a user doesn't
# have one installed locally yet - this saves a bunch of time then
ADD https://www.ietf.org/lib/dt/sprint/ietf_utf8.sql.gz /
RUN pigz -v -d /ietf_utf8.sql.gz && \
    sed -i -e 's/ENGINE=MyISAM/ENGINE=InnoDB/' /ietf_utf8.sql
# see https://dba.stackexchange.com/a/83385
RUN sed -i 's/\[mysqld\]/\[mysqld\]\ninnodb_buffer_pool_size = 1G\ninnodb_log_buffer_size = 128M\ninnodb_log_file_size = 256M\ninnodb_write_io_threads = 8\ninnodb_flush_log_at_trx_commit = 0/' /etc/mysql/mariadb.conf.d/50-server.cnf && \
    service mariadb start --innodb-doublewrite=0 && \
    echo "This sequence will take a long time, please be patient" && \
    mysqladmin -u root --default-character-set=utf8 create ietf_utf8 && \
    bash -c "cd /mariadb-sys-master && mysql --user root < sys_10.sql" && \
    bash -c "mysql --user root ietf_utf8 <<< \"GRANT ALL PRIVILEGES ON *.* TO django@localhost IDENTIFIED BY 'RkTkDPFnKpko'; FLUSH PRIVILEGES;\"" && \
    bash -c "mysql --user=django --password=RkTkDPFnKpko -f ietf_utf8 < /ietf_utf8.sql" && \
    service mariadb stop && \
    sed -i 's/^innodb_.*//g' /etc/mysql/mariadb.conf.d/50-server.cnf && \
    rm -rf /ietf_utf8.sql /mariadb-sys-master && \
    mv /var/lib/mysql /

# Copy the startup file
COPY docker-init.sh /docker-init.sh
RUN chmod +x /docker-init.sh

WORKDIR /root/src
ENTRYPOINT ["/docker-init.sh"]