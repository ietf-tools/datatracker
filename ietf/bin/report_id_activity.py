#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- Python -*-
#

# Set PYTHONPATH and load environment variables for standalone script -----------------
import os, sys
basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path = [ basedir ] + sys.path
os.environ["DJANGO_SETTINGS_MODULE"] = "ietf.settings"

virtualenv_activation = os.path.join(basedir, "bin", "activate_this.py")
if os.path.exists(virtualenv_activation):
    execfile(virtualenv_activation, dict(__file__=virtualenv_activation))

import django
django.setup()
# -------------------------------------------------------------------------------------

from ietf.secr.drafts.reports import report_id_activity

print report_id_activity(sys.argv[1], sys.argv[2]),

