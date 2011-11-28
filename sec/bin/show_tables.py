#!/usr/bin/python

from django.core.management import setup_environ
from sec import settings

setup_environ(settings)

from django.core.management.sql import sql_create
from django.core.management.color import color_style, no_style
from django.conf import settings
from django.db import models
from django.db.models.loading import cache

# another way to iterate over apps
#for apps in cache.get_apps():
#    app.__name__
import re
import sys

re_create=re.compile(r"CREATE TABLE `(.*)`.*")
app_labels = []
commands = []
tables = set()

if len(sys.argv) == 2:
    app_labels = [sys.argv[1]]
else:
    for a in settings.INSTALLED_APPS:
	if a.startswith('ietf'):
	    proj,app_label = a.split('.')
            app_labels.append(app_label)

for app_label in app_labels:
    app = models.get_app(app_label)
    commands.extend(sql_create(app,no_style()))

for line in commands:
     match=re_create.match(line)
     if match:
         tables.add(match.groups()[0])

print sorted(tables)
