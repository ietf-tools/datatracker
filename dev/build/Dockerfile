FROM ghcr.io/ietf-tools/datatracker-app-base:latest
LABEL maintainer="IETF Tools Team <tools-discuss@ietf.org>"

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get purge -y imagemagick imagemagick-6-common

COPY . .
COPY ./dev/build/start.sh ./datatracker-start.sh
COPY ./dev/celery/docker-init.sh /celery-start.sh

RUN pip3 --disable-pip-version-check --no-cache-dir install -r requirements.txt
RUN pip3 --disable-pip-version-check --no-cache-dir install watchdog[watchmedo]

RUN chmod +x datatracker-start.sh && \
    chmod +x celery-start.sh \
    chmod +x docker/scripts/app-create-dirs.sh && \
    sh ./docker/scripts/app-create-dirs.sh

VOLUME [ "/assets" ]

EXPOSE 8000

CMD ["./datatracker-start.sh"]
