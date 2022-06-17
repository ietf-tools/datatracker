#!/bin/bash

# Usage info
show_help() {
    cat << EOF
Usage: ${0##*/} [-h] [-p PATH] [-q]
Fetch all assets using rsync

    -h          display this help and exit
    -p PATH     set a custom destination path
    -q          quiet mode, don't show progress stats

EOF
}

DEST_ROOT=/assets
PROGRESS=1

while getopts "hp:q" opt; do
    case $opt in
        h)
            show_help
            exit 0
            ;;
        p)  
            DEST_ROOT=$OPTARG
            ;;
        q)
            unset PROGRESS
            ;;
    esac
done

echo "Using destination $DEST_ROOT"

EXCLUDE="$(mktemp)"
cat << EOF > "$EXCLUDE"
*#
*%
*.1
*.cgi
*.diff
*.doc
*.exe
*.html
*.json
*.mib
*.new
*.p7s
*.pdf
*.ps
*.tar
*.utf8
*.xml
*.Z
*.zip
*~
/09nov
/10[0-9]
/[0-9][0-9]
/bcp
/beta
/fyi
/ien
/inline-errata
/interim-20[01][0-9]-*
/pending-errata
/prerelease
/std
/v3test
rfc[0-9]
rfc[0-9][0-9]
rfc[0-9][0-9][0-9]
rfc[0-9][0-9][0-9][0-9]
EOF

OPTS="-asz --no-owner --no-group --partial ${PROGRESS:+--info=progress2} --exclude-from=$EXCLUDE --del --delete-excluded"

for dir in bofreq; do
    dest="$DEST_ROOT/ietf-ftp/$dir"
    mkdir -p "$dest"
    echo "Fetching $dest ..."
    rsync $OPTS rsync.ietf.org::$dir/ $dest/
done

for dir in charter conflict-reviews internet-drafts review rfc slides status-changes yang; do
    dest="$DEST_ROOT/ietf-ftp/$dir"
    mkdir -p "$dest"
    echo "Fetching $dest ..."
    rsync $OPTS rsync.ietf.org::everything-ftp/$dir/ $dest/
done

for dir in floor photo; do
    dest="$DEST_ROOT/media/$dir"
    mkdir -p "$dest"
    echo "Fetching $dest ..."
    rsync $OPTS rsync.ietf.org::dev.media/$dir/ $dest/
done

dest="$DEST_ROOT/archive/id"
mkdir -p "$dest"
echo "Fetching $dest ..."
rsync $OPTS rsync.ietf.org::id-archive/ $dest/

dest="$DEST_ROOT/www6s/proceedings"
mkdir -p "$dest"
echo "Fetching $dest ..."
rsync $OPTS rsync.ietf.org::proceedings/ $dest/

rm "$EXCLUDE"
