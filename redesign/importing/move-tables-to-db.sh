#!/bin/bash
#
# usage: move-tables-to-db.sh old-db-name new-db-name
#
# Do the grunt work of moving tables from old-db-name to new-db-name,
# the new database is created if it doesn't exist. Note that
# permissions on the old database are not moved (so the old ones are
# kept, and the new database won't have any).

OLD_DB=$1
NEW_DB=$2

# read access info at start so we don't get asked a gazillion times about them by MySQL

read -p "MySQL user: " MYSQL_USER
read -s -p "MySQL password for \"$MYSQL_USER\": " MYSQL_PASSWORD

MYSQL_CMD="mysql -NB -u $MYSQL_USER --password=$MYSQL_PASSWORD"

echo .

echo "Extracting table names"

TABLES=`echo "SHOW TABLES IN $1;" | $MYSQL_CMD | sed -e 's/^/\`/' -e 's/$/\`/'`

echo "Found `echo \"$TABLES\" | wc -l` tables"


echo "Creating database \`$NEW_DB\`"

echo "CREATE DATABASE \`$NEW_DB\`;" | $MYSQL_CMD


echo "Moving tables from \`$OLD_DB\` to \`$NEW_DB\`"

for TABLE in $TABLES; do
    echo "RENAME TABLE \`$OLD_DB\`.$TABLE TO \`$NEW_DB\`.$TABLE;" | $MYSQL_CMD
done

echo "Done"
