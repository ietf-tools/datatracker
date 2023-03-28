export DEBIAN_FRONTEND=noninteractive

echo "Fixing permissions..."
chmod -R 777 ./

echo "Ensure all requirements.txt packages are installed..."
pip --disable-pip-version-check --no-cache-dir install -r requirements.txt

echo "Creating data directories..."
chmod +x ./docker/scripts/app-create-dirs.sh
./docker/scripts/app-create-dirs.sh

# Add Postgresql Apt Repository to get 14    
echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" | tee /etc/apt/sources.list.d/pgdg.list
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add -

# Install pg client and pgloader
apt-get update
apt-get install -y --no-install-recommends postgresql-client-14 pgloader
    
# Wait for DB containers
echo "Waiting for DB containers to come online..."
/usr/local/bin/wait-for db:3306 -- echo "MariaDB ready"
/usr/local/bin/wait-for pgdb:5432 -- echo "PostgreSQL ready"

# Set up schema and alter search path
psql -U django -h pgdb -d ietf -v ON_ERROR_STOP=1 -c '\x' \
  -c 'DROP SCHEMA IF EXISTS ietf_utf8 CASCADE;' \
  -c 'CREATE SCHEMA ietf_utf8;' \
  -c 'ALTER DATABASE ietf SET search_path=ietf_utf8,public;' \
  -c 'ALTER USER django set search_path=ietf_utf8,django,public;' \
  -c 'CREATE EXTENSION citext WITH SCHEMA ietf_utf8;'

# Copy settings files
cp ./docker/configs/settings_local.py ./ietf/settings_local.py
cp ./docker/configs/settings_mysqldb.py ./ietf/settings_mysqldb.py
cp ./docker/configs/settings_postgresqldb.py ./ietf/settings_postgresqldb.py

# Switch to PostgreSQL config
#cat ./ietf/settings_local.py | sed 's/from ietf.settings_mysqldb import DATABASES/from ietf.settings_postgresqldb import DATABASES/' > /tmp/settings_local.py && mv /tmp/settings_local.py ./ietf/settings_local.py
cat ./ietf/settings_postgresqldb.py | sed "s/'db'/'pgdb'/" > /tmp/settings_postgresqldb.py && mv /tmp/settings_postgresqldb.py ./ietf/settings_postgresqldb.py

# Migrate empty schema into postgres database
/usr/local/bin/python ./ietf/manage.py check --settings=settings_local
/usr/local/bin/python ./ietf/manage.py migrate --settings=settings_local

# Now transfer data from mysql to postgres
echo "Transferring migrated database from MySQL to PostgreSQL..."
cat << EOF > transforms.lisp
; transform functions for IETF datatracker conversion
(in-package :pgloader.transforms)
(defun integer-to-interval (dt)
  "Convert microseconds to a postgres interval value"
  (multiple-value-bind (totsec useconds) (floor (parse-integer dt) 1000000)
    (multiple-value-bind (totmin seconds) (floor totsec 60)
      (multiple-value-bind (tothours minutes) (floor totmin 60)
        (multiple-value-bind (totdays hours) (floor tothours 24)
          (multiple-value-bind (totmonths days) (floor totdays 30)
            (multiple-value-bind (years months) (floor totmonths 12)
              (format nil "~a years ~a months ~a days ~a hours ~a minutes ~a seconds ~a microseconds"
                      years months days hours minutes seconds useconds))))))))
EOF
cat << EOF > cast.load
LOAD DATABASE
FROM mysql://django:RkTkDPFnKpko@db/ietf_utf8
INTO postgresql://django:RkTkDPFnKpko@pgdb/ietf
WITH workers = 3, concurrency = 1, batch size = 1MB, batch rows = 1000,
     data only, truncate, include no drop, create no tables, create no indexes, reset sequences
EXCLUDING TABLE NAMES MATCHING
    'django_migrations',
    'community_communitylist_added_ids',
    'community_documentchangedates',
    'community_expectedchange',
    'community_listnotification',
    'community_rule_cached_ids',
    'draft_versions_mirror',
    'iesg_wgaction',
    'ietfworkflows_annotationtag',
    'ietfworkflows_statedescription',
    'ietfworkflows_stream',
    'ietfworkflows_wgworkflow',
    'ipr_iprselecttype',
    'ipr_iprlicensing',
    'request_profiler_profilingrecord',
    'request_profiler_ruleset',
    'south_migrationhistory',
    'submit_idapproveddetail',
    'workflows_state',
    'workflows_state_transitions',
    'workflows_transition',
    'workflows_workflow'
CAST TYPE int with extra auto_increment TO integer,
     TYPE int TO integer,
     COLUMN django_admin_log.action_flag TO smallint,
     COLUMN meeting_session_materials.order TO smallint,
     COLUMN community_emailsubscription.email_id TO text,
     COLUMN doc_dochistory.shepherd_id TO text,
     COLUMN doc_document.shepherd_id TO text,
     COLUMN doc_documentauthor.email_id TO text,
     COLUMN doc_dochistoryauthor.email_id TO text,
     COLUMN group_role.email_id TO text,
     COLUMN group_rolehistory.email_id TO text,
     COLUMN liaisons_liaisonstatement.from_contact_id TO text,
     COLUMN nomcom_nominee.email_id TO text,
     COLUMN person_email.address TO text,
     COLUMN person_historicalemail.address TO text,
     COLUMN review_historicalreviewassignment.reviewer_id TO text,
     COLUMN review_reviewassignment.reviewer_id TO text,
     COLUMN meeting_session.requested_duration TO interval USING integer-to-interval,
     COLUMN meeting_timeslot.duration TO interval USING integer-to-interval,
     COLUMN meeting_meeting.idsubmit_cutoff_time_utc TO interval USING integer-to-interval,
     COLUMN meeting_meeting.idsubmit_cutoff_warning_days TO interval USING integer-to-interval
BEFORE LOAD DO
  -- must change person_email before any tables with FK constraints to address
  \$\$ ALTER TABLE person_email ALTER COLUMN address TYPE text; \$\$,
  \$\$ ALTER TABLE community_emailsubscription ALTER COLUMN email_id TYPE text; \$\$,
  \$\$ ALTER TABLE doc_dochistory ALTER COLUMN shepherd_id TYPE text; \$\$,
  \$\$ ALTER TABLE doc_document ALTER COLUMN shepherd_id TYPE text; \$\$,
  \$\$ ALTER TABLE doc_documentauthor ALTER COLUMN email_id TYPE text; \$\$,
  \$\$ ALTER TABLE doc_dochistoryauthor ALTER COLUMN email_id TYPE text; \$\$,
  \$\$ ALTER TABLE group_role ALTER COLUMN email_id TYPE text; \$\$,
  \$\$ ALTER TABLE group_rolehistory ALTER COLUMN email_id TYPE text; \$\$,
  \$\$ ALTER TABLE liaisons_liaisonstatement ALTER COLUMN from_contact_id TYPE text; \$\$,
  \$\$ ALTER TABLE nomcom_nominee ALTER COLUMN email_id TYPE text; \$\$,
  \$\$ ALTER TABLE person_historicalemail ALTER COLUMN address TYPE text; \$\$,
  \$\$ ALTER TABLE review_historicalreviewassignment ALTER COLUMN reviewer_id TYPE text; \$\$,
  \$\$ ALTER TABLE review_reviewassignment ALTER COLUMN reviewer_id TYPE text; \$\$
AFTER LOAD DO
  \$\$ ALTER TABLE community_emailsubscription ALTER COLUMN email_id TYPE citext; \$\$,
  \$\$ ALTER TABLE doc_dochistory ALTER COLUMN shepherd_id TYPE citext; \$\$,
  \$\$ ALTER TABLE doc_document ALTER COLUMN shepherd_id TYPE citext; \$\$,
  \$\$ ALTER TABLE doc_documentauthor ALTER COLUMN email_id TYPE citext; \$\$,
  \$\$ ALTER TABLE doc_dochistoryauthor ALTER COLUMN email_id TYPE citext; \$\$,
  \$\$ ALTER TABLE group_role ALTER COLUMN email_id TYPE citext; \$\$,
  \$\$ ALTER TABLE group_rolehistory ALTER COLUMN email_id TYPE citext; \$\$,
  \$\$ ALTER TABLE liaisons_liaisonstatement ALTER COLUMN from_contact_id TYPE citext; \$\$,
  \$\$ ALTER TABLE nomcom_nominee ALTER COLUMN email_id TYPE citext; \$\$,
  \$\$ ALTER TABLE person_historicalemail ALTER COLUMN address TYPE citext; \$\$,
  \$\$ ALTER TABLE review_historicalreviewassignment ALTER COLUMN reviewer_id TYPE citext; \$\$,
  \$\$ ALTER TABLE review_reviewassignment ALTER COLUMN reviewer_id TYPE citext; \$\$,
  -- must change person_email after any tables with FK constraints to address
  \$\$ ALTER TABLE person_email ALTER COLUMN address TYPE citext; \$\$
;
EOF
pgloader --verbose --logfile=ietf_pgloader.run --summary=ietf_pgloader.summary --load-lisp-file transforms.lisp cast.load
rm cast.load transforms.lisp

# Create export dump
echo "Creating export dump..."
pg_dump -h pgdb -U django -F c ietf > ietf.dump

echo "Done."
