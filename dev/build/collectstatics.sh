#!/bin/bash
# Copyright The IETF Trust 2024. All Rights Reserved.

# Copy temp local settings
cp dev/build/settings_local_collectstatics.py ietf/settings_local.py

# Install Python dependencies
pip --disable-pip-version-check --no-cache-dir install -r requirements.txt

# Collect statics
ietf/manage.py collectstatic

# Delete temp local settings
rm ietf/settings_local.py
