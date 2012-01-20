from django.conf import settings
from ietf.meeting.models import Meeting

import os

CURRENT_MEETING = Meeting.objects.order_by('-number')[0]

def get_upload_root(meeting):
    path = ''
    if meeting.type.slug == 'ietf':
        path = os.path.join(settings.PROCEEDINGS_DIR,meeting.number)
    elif meeting.type.slug == 'interim':
        path = os.path.join(settings.MEDIA_ROOT,
                            'proceedings/interim',
                            meeting.date.strftime('%Y'),
                            meeting.date.strftime('%m'),
                            meeting.date.strftime('%d'),
                            meeting.timeslot_set.all()[0].session.group.acronym)
    return path
