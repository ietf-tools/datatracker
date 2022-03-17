#!/bin/bash

for sub in \
    test/id \
    test/staging \
    test/archive \
    test/rfc \
    test/media \
    test/wiki/ietf \
    data/nomcom_keys/public_keys \
    data/developers/ietf-ftp \
    data/developers/ietf-ftp/bofreq \
    data/developers/ietf-ftp/charter \
    data/developers/ietf-ftp/conflict-reviews \
    data/developers/ietf-ftp/internet-drafts \
    data/developers/ietf-ftp/rfc \
    data/developers/ietf-ftp/status-changes \
    data/developers/ietf-ftp/yang/catalogmod \
    data/developers/ietf-ftp/yang/draftmod \
    data/developers/ietf-ftp/yang/ianamod \
    data/developers/ietf-ftp/yang/invalmod \
    data/developers/ietf-ftp/yang/rfcmod \
    data/developers/www6s \
    data/developers/www6s/staging \
    data/developers/www6s/wg-descriptions \
    data/developers/www6s/proceedings \
    data/developers/www6/ \
    data/developers/www6/iesg \
    data/developers/www6/iesg/evaluation \
    data/developers/media/photo \
    ; do
    if [ ! -d "$sub"  ]; then
        echo "Creating dir $sub"
        mkdir -p "$dir";
    fi
done
