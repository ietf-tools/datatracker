from ietf.group.models import Group

from ietf.ietfauth.decorators import has_role

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
    
    if has_role(user,'Secretariat'):
        return Group.objects.active_wgs().order_by('acronym')
        
    elif has_role(user,'Area Director'):
        # we are assuming one person will not be area director for more than one area
        return Group.objects.active_wgs().filter(parent=person.role_set.get(name__name='Area Director').group).order_by('acronym')
        
    elif has_role(user,['WG Chair','WG Secretary']):
        return Group.objects.active_wgs().filter(role__person=person,role__name__in=('chair','secr')).order_by('acronym')

    # otherwise return empty list
    return []