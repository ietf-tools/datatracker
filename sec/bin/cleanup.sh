#!/bin/bash

# script to run the cleanup management command
# to truncate the django_sessions table

export PYTHONPATH=/a/www/ietfsec/current:/a/www/ietf-datatracker/web
cd /a/www/ietfsec/current/sec/
/usr/bin/python manage.py cleanup
