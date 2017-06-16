import os

from django.conf import settings

from ietf.meeting.models import Meeting, Session

def get_current_meeting():
    '''Returns the most recent IETF meeting'''
    return Meeting.objects.filter(type='ietf').order_by('-number')[0]
    
def get_materials(group,meeting):
    '''
    Returns the materials as a dictionary with keys = doctype.
    NOTE, if the group has multiple sessions all materials but recordings will be
    attached to all sessions.
    '''
    materials = dict(slides=[],recording=[],bluesheets=[])
    # TODO: status should only be sched, but there is a bug in the scheduler
    for session in Session.objects.filter(group=group,meeting=meeting,status__in=('sched','schedw')):
        for doc in session.materials.exclude(states__slug='deleted').order_by('order'):
            if doc.type.slug in ('minutes','agenda'):
                materials[doc.type.slug] = doc
            elif doc.type.slug == 'draft':
                continue
                # drafts are currently managed directly by the session and document views
            elif doc not in materials[doc.type.slug]:
                materials[doc.type.slug].append(doc)
    return materials

def get_proceedings_path(meeting,group):
    if meeting.type_id == 'ietf':
        path = os.path.join(meeting.get_materials_path(),group.acronym + '.html')
    elif meeting.type_id == 'interim':
        path = os.path.join(meeting.get_materials_path(),'proceedings.html')
    return path

def get_proceedings_url(meeting,group=None):
    url = '%sproceedings/%s/' % (settings.IETF_HOST_URL,meeting.number)
    if meeting.type_id == 'ietf' and group:
        url = url + '%s.html' % group.acronym
    elif meeting.type_id == 'interim':
        url = url + 'proceedings.html'
    return url
    
def get_session(timeslot, schedule=None):
    '''
    Helper function to get the session given a timeslot, assume Official schedule if one isn't
    provided.  Replaces "timeslot.session"
    '''
    # todo, doesn't account for shared timeslot
    if not schedule:
        schedule = timeslot.meeting.agenda
    qs = timeslot.sessions.filter(timeslotassignments__schedule=schedule)  #.exclude(states__slug='deleted')
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
    ss = session.timeslotassignments.filter(schedule=schedule)
    if ss:
        return ss[0].timeslot
    else:
        return None

