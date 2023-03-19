FROM alpine:3

RUN apk add --no-cache wget rsync
COPY docker/scripts/app-rsync-extras.sh /workspace/app-rsync-extras.sh
RUN chmod +x /workspace/app-rsync-extras.sh

WORKDIR /workspace

CMD ["sh", "app-rsync-extras.sh"]
