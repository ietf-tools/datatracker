from ietf.group.models import Group

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