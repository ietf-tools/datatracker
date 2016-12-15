#!/usr/bin/env python

import os
import sys
import warnings

warnings.simplefilter("always", DeprecationWarning)
warnings.filterwarnings("ignore", message="Passing callable arguments to queryset is deprecated.", module="django.db.models.sql.query", lineno=1156)
warnings.filterwarnings("ignore", message="`MergeDict` is deprecated, use `dict.update()` instead.", module="django.core.handlers.wsgi", lineno=126)
warnings.filterwarnings("ignore", message="The app_mod argument of get_models is deprecated.", module="django.utils.lru_cache", lineno=101)
warnings.filterwarnings("ignore", message="Report.file_reporters will no longer be available in Coverage.py 4.2", module="coverage.report", lineno=43)

path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if not path in sys.path:
    sys.path.insert(0, path)

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
