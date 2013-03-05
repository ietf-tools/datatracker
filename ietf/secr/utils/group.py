from django.conf import settings
from ietf.group.models import Group
from ietf.meeting.models import Session

from ietf.ietfauth.decorators import has_role

import itertools
import os

def current_nomcom():
    qs = Group.objects.filter(acronym__startswith='nomcom',state__name="Active").order_by('-time')
    return qs[0]

def get_charter_text(group):
    '''
    Takes a group object and returns the text or the group's charter as a string
    '''
    charter = group.charter
    path = os.path.join(settings.CHARTER_PATH, '%s-%s.txt' % (charter.canonical_name(), charter.rev))
    f = file(path,'r')
    text = f.read()
    f.close()
    
    return text
    
def get_my_groups(user,conclude=False):
    '''
    Takes a Django user object (from request)
    Returns a list of groups the user has access to.  Rules are as follows
    secretariat - has access to all groups
    area director - has access to all groups in their area
    wg chair or secretary - has acceses to their own group
    chair of irtf has access to all irtf groups
    
    If user=None than all groups are returned.
    concluded=True means include concluded groups.  Need this to upload materials for groups
    after they've been concluded.  it happens.
    '''
    my_groups = set()
    states = ['bof','proposed','active']
    if conclude: 
        states.append('conclude')
    all_groups = Group.objects.filter(type__in=('wg','rg','ag','team'),state__in=states).order_by('acronym')
    if user == None:
        return all_groups
    else:
        person = user.get_profile()
    
    if has_role(user,'Secretariat'):
        return all_groups
    
    for group in all_groups:
        if group.role_set.filter(person=person,name__in=('chair','secr')):
            my_groups.add(group)
            continue
        if group.parent and group.parent.role_set.filter(person=person,name__in=('ad','chair')):
            my_groups.add(group)
            continue
    
    return list(my_groups)
    
def groups_by_session(user, meeting):
    '''
    Takes a Django User object and a Meeting object
    Returns a tuple scheduled_groups, unscheduled groups.  sorted lists of those groups that 
    the user has access to, secretariat defaults to all groups
    If user=None than all groups are returned.
    
    For groups with a session, we must include "concluded" groups because we still want to know
    who had a session at a particular meeting even if they are concluded after.  This is not true
    for groups without a session because this function is often used to build select lists (ie.
    Session Request Tool) and you don't want concluded groups appearing as options.
    '''
    groups_session = []
    groups_no_session = []
    my_groups = get_my_groups(user,conclude=True)
    sessions = Session.objects.filter(meeting=meeting,status__in=('schedw','apprw','appr','sched'))
    groups_with_sessions = [ s.group for s in sessions ]
    for group in my_groups:
        if group in groups_with_sessions:
            groups_session.append(group)
        else:
            if group.state_id != 'conclude':
                groups_no_session.append(group)
            
    return groups_session, groups_no_session
    