FROM ghcr.io/ietf-tools/datatracker-app-base:latest
LABEL maintainer="IETF Tools Team <tools-discuss@ietf.org>"

ENV DEBIAN_FRONTEND=noninteractive

# uid 498 = wwwrun and gid 496 = www on ietfa
RUN groupadd -g 1000 datatracker && \
    useradd -c "Datatracker User" -u 1000 -g datatracker -m -s /bin/false datatracker

RUN apt-get purge -y imagemagick imagemagick-6-common

# Install libreoffice (needed via PPT2PDF_COMMAND)
RUN echo "deb http://deb.debian.org/debian bullseye-backports main" > /etc/apt/sources.list.d/bullseye-backports.list && \
    apt-get update && \
    apt-get -qyt bullseye-backports install libreoffice-nogui

COPY . .
COPY ./dev/build/start.sh ./start.sh
COPY ./dev/build/datatracker-start.sh ./datatracker-start.sh
COPY ./dev/build/migration-start.sh ./migration-start.sh
COPY ./dev/build/celery-start.sh ./celery-start.sh
COPY ./dev/build/gunicorn.conf.py ./gunicorn.conf.py

RUN pip3 --disable-pip-version-check --no-cache-dir install -r requirements.txt && \
    echo '# empty' > ietf/settings_local.py && \
    ietf/manage.py patch_libraries && \
    rm -f ietf/settings_local.py

RUN chmod +x start.sh && \
    chmod +x datatracker-start.sh && \
    chmod +x migration-start.sh && \
    chmod +x celery-start.sh && \
    chmod +x docker/scripts/app-create-dirs.sh && \
    sh ./docker/scripts/app-create-dirs.sh

RUN mkdir -p /a

VOLUME [ "/a" ]

EXPOSE 8000

CMD ["./start.sh"]
