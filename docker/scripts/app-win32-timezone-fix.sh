#!/bin/bash

WORKSPACEDIR="/root/src"

ICSFILES=$(/usr/bin/find $WORKSPACEDIR/vzic/zoneinfo/ -name '*.ics' -print)
for ICSFILE in $ICSFILES
do
    LINK=$(head -n1 $ICSFILE | sed -e '/link .*/!d' -e 's/link \(.*\)/\1/')
    if [ "$LINK" ]; then
        WDIR=$(dirname $ICSFILE)
        echo "Replacing $(basename $ICSFILE) with $LINK"
        cp -f $WDIR/$LINK $ICSFILE
    fi
done
echo "Done!"