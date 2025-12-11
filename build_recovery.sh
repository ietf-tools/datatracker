#!/bin/bash

# load the older production dump (a compressed binary form)
# dump a plaintext “before.sql”
# delete the target Email object
# dump a plaintext “after.sql”
# remove COPY statements from “after.sql” to create “after_nocopy.sql”
# diff before and after_nocopy
# processes the diff with python to create "recovery.sql"
#    extract the COPY statements from the diff
#    reorder the tables to avoid foreign key violations as rows are loaded
# cat “recovery.sql” intto psql
# dump a plaintext “recovered.sql”
# diff “before” and “recovered”
# process the diff ignoring expected differences and reporting on any surprises

echo "Restoring older production dump..."
pg_restore -c -h db -U django -d datatracker 2025-12-08T0640.dump 2>&1 | grep -v 'role "datatracker" does not exist' | grep -v "OWNER TO datatracker" | grep -v "^$"
echo "Dumping plaintext 'before.sql'..."
pg_dump -c -h db -U django -d datatracker -f before.sql
echo
echo "from ietf.person.models import Email; Email.objects.filter(address='shares@ndzh.com.').delete()" | ./ietf/manage.py shell
echo
pg_dump -c -h db -U django -d datatracker -f after.sql
echo "Building recovery.sql..."
cat after.sql | grep -v "^COPY " > after_nocopy.sql
diff before.sql after_nocopy.sql > diff_recovery.txt
python extract_recovery.py diff_recovery.txt recovery.sql
echo "Applying recovery.sql..."
psql -h db -U django -d datatracker -f recovery.sql
echo "Dumping plaintext 'recovered.sql'..."
pg_dump -c -h db -U django -d datatracker -f recovered.sql
echo "Building recovery report..."
cat recovered.sql | grep -v "^COPY " > recovered_nocopy.sql
diff before.sql recovered_nocopy.sql > diff_recovered.txt
# python recovery_report.py diff_recovered.txt
