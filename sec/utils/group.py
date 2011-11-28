from redesign.group.models import Group

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
        my_groups = Group.objects.active.all()
        
    elif has_role(user,'Area Director'):
        # we are assuming one person will not be area director for more than one area
        my_groups = Group.objects.active.filter(parent=person.role_set.get(name__name='Area Director').group)
        
    elif has_role(user,['WG Chair','WG Secretary']):
        my_groups = Group.objects.active.filter(role__in=Role.objects.filter(person=person,name__in=('Chair','Secretary')))
        
    return my_groups