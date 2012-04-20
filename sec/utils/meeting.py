from django.conf import settings
from ietf.meeting.models import Meeting

import os

def get_current_meeting():
    '''Returns the most recent IETF meeting'''
    return Meeting.objects.filter(type='ietf').order_by('-number')[0]
    
def get_material(session):
    '''
    This function takes a session object and returns a tuple of active materials:
    agenda(Document), minutes(Document), slides(list of Documents)
    '''
    active_materials = session.materials.exclude(states__slug='deleted')
    slides = active_materials.filter(type='slides').order_by('order')
    minutes = active_materials.filter(type='minutes')
    minutes = minutes[0] if minutes else None
    agenda = active_materials.filter(type='agenda')
    agenda = agenda[0] if agenda else None
    
    return agenda,minutes,slides

def get_proceedings_path(meeting, group):
    if meeting.type.slug == 'interim':
        path = os.path.join(get_upload_root(meeting),'proceedings.html')
    else:
        path = os.path.join(get_upload_root(meeting),'%s.html' % group.acronym)
    return path
    
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