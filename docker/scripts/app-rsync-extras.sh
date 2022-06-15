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

for dir in bofreq; do
    dest="$DEST_ROOT/ietf-ftp/$dir"
    mkdir -p "$dest"
    echo "Fetching $dest ..."
    rsync -auz ${PROGRESS:+--info=progress2} rsync.ietf.org::$dir/ $dest/
done

for dir in charter conflict-reviews internet-drafts review rfc slides status-changes yang; do
    dest="$DEST_ROOT/ietf-ftp/$dir"
    mkdir -p "$dest"
    echo "Fetching $dest ..."
    rsync -auz ${PROGRESS:+--info=progress2} rsync.ietf.org::everything-ftp/$dir/ $dest/
done

for dir in floor photo; do
    dest="$DEST_ROOT/media/$dir"
    mkdir -p "$dest"
    echo "Fetching $dest ..."
    rsync -auz ${PROGRESS:+--info=progress2} rsync.ietf.org::dev.media/$dir/ $dest/
done

dest="$DEST_ROOT/archive/id"
mkdir -p "$dest"
echo "Fetching $dest ..."
rsync -auz ${PROGRESS:+--info=progress2} rsync.ietf.org::id-archive/ $dest/

dest="$DEST_ROOT/www6s/proceedings"
mkdir -p "$dest"
echo "Fetching $dest ..."
rsync -auz ${PROGRESS:+--info=progress2} rsync.ietf.org::proceedings/ $dest/
