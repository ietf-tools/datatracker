
import site
site.addsitedir('/data/pythonenv/IETFDB/lib/python2.6/site-packages')

import os, sys

sys.path.append('/data/orlando/orlando/current')
os.environ['DJANGO_SETTINGS_MODULE'] = 'ietf.settings'

import django.core.handlers.wsgi
application = django.core.handlers.wsgi.WSGIHandler()

