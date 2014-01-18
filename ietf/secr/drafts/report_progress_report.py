import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ietf.settings")

from ietf.secr.drafts.views import report_progress_report 
import sys

print report_progress_report(sys.argv[1], sys.argv[2]),

