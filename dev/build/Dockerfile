FROM ghcr.io/ietf-tools/datatracker-app-base:latest
LABEL maintainer="IETF Tools Team <tools-discuss@ietf.org>"

ENV DEBIAN_FRONTEND=noninteractive

COPY . .
COPY ./dev/build/start.sh ./start.sh
RUN pip3 --disable-pip-version-check --no-cache-dir install -r requirements.txt
RUN chmod +x start.sh && \
    chmod +x docker/scripts/app-create-dirs.sh && \
    sh ./docker/scripts/app-create-dirs.sh

VOLUME [ "/assets" ]

EXPOSE 8000

CMD ["./start.sh"]