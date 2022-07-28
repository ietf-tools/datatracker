# =====================
# --- Builder Stage ---
# =====================
FROM mariadb:10 AS builder

# That file does the DB initialization but also runs mysql daemon, by removing the last line it will only init
RUN ["sed", "-i", "s/exec \"$@\"/echo \"not running $@\"/", "/usr/local/bin/docker-entrypoint.sh"]

# needed for intialization
ENV MARIADB_ROOT_PASSWORD=RkTkDPFnKpko
ENV MARIADB_DATABASE=ietf_utf8
ENV MARIADB_USER=django
ENV MARIADB_PASSWORD=RkTkDPFnKpko

# Import the latest database dump
ADD https://www.ietf.org/lib/dt/sprint/ietf_utf8.sql.gz /docker-entrypoint-initdb.d/

# Need to change the datadir to something else that /var/lib/mysql because the parent docker file defines it as a volume.
# https://docs.docker.com/engine/reference/builder/#volume :
#       Changing the volume from within the Dockerfile: If any build steps change the data within the volume after
#       it has been declared, those changes will be discarded.
RUN ["/usr/local/bin/docker-entrypoint.sh", "mysqld", "--datadir", "/initialized-db", "--aria-log-dir-path", "/initialized-db"]

# ===================
# --- Final Image ---
# ===================
FROM mariadb:10
LABEL maintainer="IETF Tools Team <tools-discuss@ietf.org>"

# Copy the mysql data folder from the builder stage
COPY --from=builder /initialized-db /var/lib/mysql
