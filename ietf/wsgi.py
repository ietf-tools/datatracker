# Copyright The IETF Trust 2013-2024, All Rights Reserved
# -*- coding: utf-8 -*-


import os
import sys

path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if not path in sys.path:
    sys.path.insert(0, path)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ietf.settings")

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
