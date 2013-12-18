import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ietf.settings")

from ietf.secr.drafts.views import report_id_activity 
import sys

print report_id_activity(sys.argv[1], sys.argv[2]),

