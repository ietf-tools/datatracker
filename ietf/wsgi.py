# Copyright The IETF Trust 2013-2021, All Rights Reserved
# -*- coding: utf-8 -*-



import os
import sys
import syslog

path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

syslog.openlog(str("datatracker"), syslog.LOG_PID, syslog.LOG_USER)

if not path in sys.path:
    sys.path.insert(0, path)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ietf.settings")

syslog.syslog("Starting datatracker wsgi instance")

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()

