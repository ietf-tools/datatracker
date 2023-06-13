# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-


# Python imports

# Django imports
from django.core.exceptions import ObjectDoesNotExist

# Datatracker imports
from ietf.group.models import Group
from ietf.ietfauth.utils import has_role


def get_my_groups(user,conclude=False):
    '''
    Takes a Django user object (from request)
    Returns a list of groups the user has access to.  Rules are as follows
    secretariat - has access to all groups
    area director - has access to all groups in their area
    wg chair or secretary - has access to their own group
    chair of irtf has access to all irtf groups

    If user=None than all groups are returned.
    concluded=True means include concluded groups.  Need this to upload materials for groups
    after they've been concluded.  it happens.
    '''
    my_groups = set()
    states = ['bof','proposed','active']
    if conclude:
        states.extend(['conclude','bof-conc'])

    all_groups = Group.objects.filter(type__features__has_meetings=True, state__in=states).order_by('acronym')
    if user == None or has_role(user,'Secretariat'):
        return all_groups
    
    try:
        person = user.person
    except ObjectDoesNotExist:
        return list()

    for group in all_groups:
        if group.role_set.filter(person=person,name__in=('chair','secr','ad')):
            my_groups.add(group)
            continue
        if group.parent and group.parent.role_set.filter(person=person,name__in=('ad','chair')):
            my_groups.add(group)
            continue

    return list(my_groups)
