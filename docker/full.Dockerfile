FROM ghcr.io/ietf-tools/datatracker-app-base:latest
LABEL maintainer="IETF Tools Team <tools-discuss@ietf.org>"

# Fetch all assets via rsync

COPY docker/scripts/app-rsync-extras.sh /rsync-assets.sh
RUN sed -i 's/\r$//' /rsync-assets.sh && \
    chmod +x /rsync-assets.sh

RUN bash /rsync-assets.sh