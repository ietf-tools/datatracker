#!/usr/bin/env python

import os
import sys

path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Virtualenv support
virtualenv_activation = os.path.join(path, "env", "bin", "activate_this.py")
if os.path.exists(virtualenv_activation):
    execfile(virtualenv_activation, dict(__file__=virtualenv_activation))
else:
    raise RuntimeError("Could not find the expected virtual python environment.")

if not path in sys.path:
    sys.path.insert(0, path)

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
