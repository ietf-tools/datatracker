from ietf.group.models import Group
from ietf.meeting.models import Session

from ietf.ietfauth.decorators import has_role

import itertools

def current_nomcom():
    return Group.objects.get(acronym__startswith='nomcom',state__name="Active")

def get_my_groups(user):
    '''
    Takes a Django user object (from request)
    Returns a list of groups the user has access to.  Rules are as follows
    secretariat - has access to all groups
    area director - has access to all groups in their area
    wg chair or secretary - has acceses to their own group
    '''
    my_groups = []
    person = user.get_profile()
    all_groups = Group.objects.filter(type__in=('wg','rg'),state__in=('bof','proposed','active')).order_by('acronym')
    
    if has_role(user,'Secretariat'):
        return all_groups
    
    # groups that person is Area Director
    ad_groups = all_groups.filter(parent__role__person=person,parent__role__name='ad')
    
    # groups that person is chair or secretary of
    groups = all_groups.filter(role__person=person,role__name__in=('chair','secr'))

    # otherwise return empty list
    return itertools.chain(ad_groups,groups)
    
def groups_by_session(user, meeting):
    '''
    Takes a Django User object and a Meeting object
    Returns a tuple scheduled_groups, unscheduled groups.  sorted lists of those groups that 
    the user has access to, secretariat defaults to all groups
    NOTE: right now get_my_groups does not inlcude RGs so they won't appear in the list
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