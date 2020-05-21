#!/a/www/ietf-datatracker/web/env/bin/python
# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-

import os
import sys

path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if not path in sys.path:
    sys.path.insert(0, path)

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
