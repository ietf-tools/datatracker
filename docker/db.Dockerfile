# =====================
# --- Builder Stage ---
# =====================
FROM postgres:16 AS builder

ENV POSTGRES_PASSWORD=hk2j22sfiv
ENV POSTGRES_USER=django
ENV POSTGRES_DB=datatracker
ENV POSTGRES_HOST_AUTH_METHOD=trust
ENV PGDATA=/data

COPY docker/scripts/db-load-default-extensions.sh /docker-entrypoint-initdb.d/
COPY docker/scripts/db-import.sh /docker-entrypoint-initdb.d/
COPY datatracker.dump /

RUN ["sed", "-i", "s/exec \"$@\"/echo \"skipping...\"/", "/usr/local/bin/docker-entrypoint.sh"]
RUN ["/usr/local/bin/docker-entrypoint.sh", "postgres"]

# ===================
# --- Final Image ---
# ===================
FROM postgres:16
LABEL maintainer="IETF Tools Team <tools-discuss@ietf.org>"

COPY --from=builder /data $PGDATA

ENV POSTGRES_PASSWORD=hk2j22sfiv
ENV POSTGRES_USER=django
ENV POSTGRES_DB=datatracker
ENV POSTGRES_HOST_AUTH_METHOD=trust
