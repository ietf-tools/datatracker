from django.conf import settings
from ietf.meeting.models import Meeting
#from sec.utils.groups import get_my_groups

import os

CURRENT_MEETING = Meeting.objects.order_by('-number')[0]

def get_upload_root(meeting):
    path = ''
    if meeting.type.slug == 'ietf':
        path = os.path.join(settings.AGENDA_PATH,meeting.number)
    elif meeting.type.slug == 'interim':
        path = os.path.join(settings.AGENDA_PATH,
                            'interim',
                            meeting.date.strftime('%Y'),
                            meeting.date.strftime('%m'),
                            meeting.date.strftime('%d'),
                            meeting.session_set.all()[0].group.acronym)
    return path

