# Use this script to generate the proceedings progress report without headers

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ietf.settings")

from ietf.secr.proceedings.proc_utils import gen_progress
from ietf.meeting.models import Meeting
import datetime


now = datetime.date.today()
meeting = Meeting.objects.filter(date__lte=now).order_by('-date')[0]
gen_progress({'meeting':meeting},final=False)
