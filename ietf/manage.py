#!/usr/bin/env python
# Copyright The IETF Trust 2007, All Rights Reserved

from django.core.management import execute_manager
try:
    import settings # Assumed to be in the same directory.
except ImportError:
    import sys
    sys.stderr.write("Error: Cannot find 'settings.py' or 'settings_local.py'.\nUsually these are in the directory containing %r.\n" % __file__)
    sys.exit(1)

if __name__ == "__main__":
    execute_manager(settings)
