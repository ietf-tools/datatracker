FROM postgres:14.5
LABEL maintainer="IETF Tools Team <tools-discuss@ietf.org>"

#RUN apt-get update \
#    && apt-get install -y --no-install-recommends \
#        postgresql-14-pg-catcheck \
#        postgresql-14-powa \
#        postgresql-14-pg-qualstats \
#        postgresql-14-pg-stat-kcache \
#        postgresql-14-pg-stat-monitor \
#        postgresql-14-pg-top \
#        postgresql-14-pg-track_settings \
#        postgresql-14-pg-wait_sampling \
#        pgsql_tweaks

ENV POSTGRES_PASSWORD=hk2j22sfiv
ENV POSTGRES_HOST_AUTH_METHOD=trust

COPY docker/scripts/pgdb-ietf-init.sh /docker-entrypoint-initdb.d/
