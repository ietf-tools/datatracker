from django.conf import settings
from ietf.meeting.models import Meeting, Session, Schedule, TimeSlot

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
    
def get_session(timeslot, schedule=None):
    '''
    Helper function to get the session given a timeslot, assume Official schedule if one isn't
    provided.  Replaces "timeslot.session"
    '''
    # todo, doesn't account for shared timeslot
    if not schedule:
        schedule = timeslot.meeting.agenda
    qs = timeslot.sessions.filter(scheduledsession__schedule=schedule)  #.exclude(states__slug='deleted')
    if qs:
        return qs[0]
    else:
        return None
    
def get_timeslot(session, schedule=None):
    '''
    Helper function to get the timeslot associated with a session.  Created for Agenda Tool
    db schema changes.  Use this function in place of session.timeslot_set.all()[0].  Don't specify
    schedule to use the meeting "official" schedule.
    '''
    if not schedule:
        schedule = session.meeting.agenda
    ss = session.scheduledsession_set.filter(schedule=schedule)
    if ss:
        return ss[0].timeslot
    else:
        return None

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