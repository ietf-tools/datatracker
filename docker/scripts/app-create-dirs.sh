#!/bin/bash

for sub in \
    test/id \
    test/staging \
    test/archive \
    test/rfc \
    test/media \
    test/wiki/ietf \
    data/nomcom_keys/public_keys \
    /assets/ietf-ftp \
    /assets/ietf-ftp/bofreq \
    /assets/ietf-ftp/charter \
    /assets/ietf-ftp/conflict-reviews \
    /assets/ietf-ftp/internet-drafts \
    /assets/ietf-ftp/rfc \
    /assets/ietf-ftp/status-changes \
    /assets/ietf-ftp/yang/catalogmod \
    /assets/ietf-ftp/yang/draftmod \
    /assets/ietf-ftp/yang/ianamod \
    /assets/ietf-ftp/yang/invalmod \
    /assets/ietf-ftp/yang/rfcmod \
    /assets/www6s \
    /assets/www6s/staging \
    /assets/www6s/wg-descriptions \
    /assets/www6s/proceedings \
    /assets/www6/ \
    /assets/www6/iesg \
    /assets/www6/iesg/evaluation \
    /assets/media/photo \
    ; do
    if [ ! -d "$sub"  ]; then
        echo "Creating dir $sub"
        mkdir -p "$sub";
    fi
done
