FROM postgres:14.5
LABEL maintainer="IETF Tools Team <tools-discuss@ietf.org>"

ENV POSTGRES_PASSWORD=hk2j22sfiv
ENV POSTGRES_HOST_AUTH_METHOD=trust

# Copy the postgres data folder from the migration stage
COPY /pg-data /var/lib/postgresql/data
