#!/bin/bash

cp dev/deploy/settings_local_collectstatics.py ietf/settings_local.py

# Install Python dependencies
pip --disable-pip-version-check --no-cache-dir install -r requirements.txt

# Collect statics
ietf/manage.py collectstatic