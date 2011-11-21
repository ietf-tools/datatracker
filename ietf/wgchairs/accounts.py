from django.conf import settings
from redesign.group.models import Role

def is_secretariat(user):
    if not user or not user.is_authenticated():
        return False
    return bool(user.groups.filter(name='Secretariat'))

    
def is_area_director_for_group(person, group):
    return bool(group.area.area.areadirector_set.filter(person=person).count())

def is_area_director_for_groupREDESIGN(person, group):
    return bool(Role.objects.filter(group=group.parent, person=person, name="ad"))


def is_group_chair(person, group):
    if group.chairs().filter(person=person):
        return True
    return False

def is_group_chairREDESIGN(person, group):
    return bool(Role.objects.filter(group=group, person=person, name="chair"))


def is_group_delegate(person, group):
    return bool(group.wgdelegate_set.filter(person=person).count())

def is_group_delegateREDESIGN(person, group):
    return bool(Role.objects.filter(group=group, person=person, name="delegate"))


def get_person_for_user(user):
    try:
        return user.get_profile().person()
    except:
        return None


if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    from ietf.liaisons.accounts import is_secretariat, get_person_for_user
    is_area_director_for_group = is_area_director_for_groupREDESIGN
    is_group_chair = is_group_chairREDESIGN
    is_group_delegate = is_group_delegateREDESIGN
    
    
def can_do_wg_workflow_in_group(user, group):
    person = get_person_for_user(user)
    if not person:
        return False
    return (is_secretariat(user) or is_group_chair(person, group))


def can_do_wg_workflow_in_document(user, document):
    person = get_person_for_user(user)
    if not person or not document.group:
        return False
    return (is_secretariat(user) or can_do_wg_workflow_in_group(document.group.ietfwg))


def can_manage_workflow_in_group(user, group):
    person = get_person_for_user(user)
    if not person:
        return False
    return (is_secretariat(user) or is_group_chair(person, group))


def can_manage_delegates_in_group(user, group):
    person = get_person_for_user(user)
    if not person:
        return False
    return (is_secretariat(user) or is_group_chair(person, group))


def can_manage_shepherds_in_group(user, group):
    person = get_person_for_user(user)
    if not person:
        return False
    return (is_secretariat(user) or is_group_chair(person, group))


def can_manage_shepherd_of_a_document(user, document):
    person = get_person_for_user(user)
    if not person or not document.group:
        return False
    return can_manage_shepherds_in_group(user, document.group.ietfwg)


def can_manage_writeup_of_a_document_no_state(user, document):
    person = get_person_for_user(user)
    if not person or not document.group:
        return False
    group = document.group.ietfwg
    return (is_secretariat(user) or
            is_group_chair(person, group) or
            is_area_director_for_group(person, group) or
            is_group_delegate(person, group))


def can_manage_writeup_of_a_document(user, document):
    person = get_person_for_user(user)
    if not person or not document.group:
        return False
    return (can_manage_writeup_of_a_document_no_state(user, document) or
            person == document.shepherd)



