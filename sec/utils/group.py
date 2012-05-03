from ietf.group.models import Group
from ietf.meeting.models import Session

from ietf.ietfauth.decorators import has_role

import itertools

def current_nomcom():
    qs = Group.objects.filter(acronym__startswith='nomcom',state__name="Active").order_by('-time')
    return qs[0]

def get_my_groups(user):
    '''
    Takes a Django user object (from request)
    Returns a list of groups the user has access to.  Rules are as follows
    secretariat - has access to all groups
    area director - has access to all groups in their area
    wg chair or secretary - has acceses to their own group
    chair of irtf has access to all irtf groups
    
    If user=None than all groups are returned.
    '''
    my_groups = set()
    all_groups = Group.objects.filter(type__in=('wg','rg','ag','team'),state__in=('bof','proposed','active')).order_by('acronym')
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
    '''
    groups_session = []
    groups_no_session = []
    my_groups = get_my_groups(user)
    sessions = Session.objects.filter(meeting=meeting,status__in=('schedw','apprw','appr','sched'))
    groups_with_sessions = [ s.group for s in sessions ]
    for group in my_groups:
            if group in groups_with_sessions:
                groups_session.append(group)
            else:
                groups_no_session.append(group)
            
    return groups_session, groups_no_session