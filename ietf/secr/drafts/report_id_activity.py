from ietf import settings
from django.core import management
management.setup_environ(settings)

from ietf.secr.drafts.views import report_id_activity 
import sys

print report_id_activity(sys.argv[1], sys.argv[2]),

