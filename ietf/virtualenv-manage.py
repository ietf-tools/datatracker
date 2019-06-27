# Copyright The IETF Trust 2016-2019, All Rights Reserved
#!/usr/bin/env python

import os
import sys

path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# change directory so patches etc. will be picked up as expected
os.chdir(path)

# Virtualenv support
virtualenv_activation = os.path.join(path, "env", "bin", "activate_this.py")
if os.path.exists(virtualenv_activation):
    exec(compile(open(virtualenv_activation, "rb").read(), virtualenv_activation, 'exec'), dict(__file__=virtualenv_activation))
else:
    raise RuntimeError("Could not find the expected virtual python environment.")

if not path in sys.path:
    sys.path.insert(0, path)

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
