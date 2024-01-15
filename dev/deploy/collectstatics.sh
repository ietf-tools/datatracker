#!/bin/bash

# Install Python dependencies
pip --disable-pip-version-check --no-cache-dir install -r requirements.txt

# Collect statics
ietf/manage.py collectstatic