#!/bin/bash

version=0.11
program=${0##*/}
progdir=${0%/*}
if [ "$progdir" = "$program" ]; then progdir="."; fi
if [ "$progdir" = "." ]; then progdir="$PWD"; fi
parent=$(dirname "$progdir")
if [ "$parent" = "." ]; then parent="$PWD"; fi
if [[ $(uname) =~ CYGWIN.* ]]; then parent=$(echo "$parent" | sed -e 's/^\/cygdrive\/\(.\)/\1:/'); fi


function usage() {
    cat <<EOF
NAME
	$program - Copy additional data files from the ietf server

SYNOPSIS
	$program [OPTIONS] [DESTINATION]

DESCRIPTION
	This script copies additional data files used by the datatracker
	from the ietf server to a local directory, for instance drafts,
	charters, rfcs, agendas, minutes, etc.

	If no destination is given, the default is data/developers.

OPTIONS
EOF
    grep -E '^\s+-[a-zA-Z])' "$0" | sed -E -e 's/\)[^#]+#/ /'
    cat <<EOF

AUTHOR
	Written by:
    	Henrik Levkowetz, <henrik@levkowetz.com>
		Lars Eggert, <lars@eggert.org>

COPYRIGHT
	Copyright (c) 2016 IETF Trust and the persons identified as authors of
	the code. All rights reserved. Redistribution and use in source and
	binary forms, with or without modification, is permitted pursuant to,
	and subject to the license terms contained in, the Revised BSD
	License set forth in Section 4.c of the IETF Trust’s Legal Provisions
	Relating to IETF Documents(https://trustee.ietf.org/license-info).

EOF
}


function die() {
    echo -e "\n$program: error: $*" >&2
    exit 1
}


function version() {
	echo -e "$program $version"
}

trap 'echo "$program($LINENO): Command failed with error code $? ([$$] $0 $*)"; exit 1' ERR


# Option parsing
shortopts=hvV
args=$(getopt -o$shortopts $*)
if [ $? != 0 ] ; then die "Terminating..." >&2 ; exit 1 ; fi
set -- $args

while true ; do
    case "$1" in
    	-h)    usage; exit;;   # Show this help, then exit
    	-v)    VERBOSE=1;;	   # Be more talkative
    	-V)    version; exit;; # Show program version, then exit
    	--)    shift; break;;
    	*) die "Internal error, inconsistent option specification: '$1'";;
    esac
    shift
done

# The program itself
if [ $# -lt 1 ]; then
    DEST_ROOT=data/developers
else
    DEST_ROOT="${1%/}"
fi
echo "Using destination $DEST_ROOT"

for dir in charter conflict-reviews internet-drafts review rfc slides status-changes yang; do
  dest="$DEST_ROOT/ietf-ftp/$dir"
  mkdir -p "$dest"
  echo "Fetching $dest ..."
  rsync -auz ${VERBOSE:+--info=progress2} rsync.ietf.org::everything-ftp/$dir/ $dest/
done

for dir in floor photo; do
  dest="$DEST_ROOT/media/$dir"
  mkdir -p "$dest"
  echo "Fetching $dest ..."
  rsync -auz ${VERBOSE:+--info=progress2} rsync.ietf.org::dev.media/$dir/ $dest/
done

dest="$DEST_ROOT/archive/id"
mkdir -p "$dest"
echo "Fetching $dest ..."
rsync -auz ${VERBOSE:+--info=progress2} rsync.ietf.org::id-archive/ $dest/