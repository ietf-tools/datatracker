ARG MINIO_VERSION=latest
FROM quay.io/minio/minio:${MINIO_VERSION}
LABEL maintainer="IETF Tools Team <tools-discuss@ietf.org>"

ENV MINIO_ROOT_USER=minio_root
ENV MINIO_ROOT_PASSWORD=minio_pass
ENV MINIO_DEFAULT_BUCKETS=defaultbucket

CMD ["server", "--console-address", ":9001", "/data"]
