from ietf import settings
from django.core import management
management.setup_environ(settings)

from ietf.secr.drafts.views import report_progress_report 
import sys

print report_progress_report(sys.argv[1], sys.argv[2]),

