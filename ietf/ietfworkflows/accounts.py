from django.conf import settings

from ietf.ietfworkflows.streams import get_streamed_draft
from redesign.group.models import Role


def get_person_for_user(user):
    try:
        return user.get_profile().person()
    except:
        return None


def is_secretariat(user):
    if not user or not user.is_authenticated():
        return False
    return bool(user.groups.filter(name='Secretariat'))


def is_wgchair(person):
    return bool(person.wgchair_set.all())

def is_wgchairREDESIGN(person):
    return bool(Role.objects.filter(name="chair", group__type="wg", group__state="active", person=person))


def is_wgdelegate(person):
    return bool(person.wgdelegate_set.all())

def is_wgdelegateREDESIGN(person):
    return bool(Role.objects.filter(name="delegate", group__type="wg", group__state="active", person=person))


def is_chair_of_draft(user, draft):
    person = get_person_for_user(user)
    if not person:
        return False
    streamed = get_streamed_draft(draft)
    if not streamed or not streamed.stream:
        return False
    group = streamed.group
    if not group or not hasattr(group, 'chairs'):
        return False
    return bool(group.chairs().filter(person=person).count())

def is_chair_of_draftREDESIGN(user, draft):
    if not user.is_authenticated() or not user.get_profile() or not draft.group:
        return False

    return bool(Role.objects.filter(name="chair", group=draft.group, person=user.get_profile()))
    
if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    from ietf.wgchairs.accounts import is_secretariat, get_person_for_user 
    is_wgdelegate = is_wgdelegateREDESIGN
    is_wgchair = is_wgchairREDESIGN
    is_chair_of_draft = is_chair_of_draftREDESIGN


def can_edit_state(user, draft):
    streamed = get_streamed_draft(draft)
    if not settings.USE_DB_REDESIGN_PROXY_CLASSES and (not streamed or not streamed.stream):
        person = get_person_for_user(user)
        if not person:
            return False
        return (is_secretariat(user) or
                is_wgchair(person) or
                is_wgdelegate(person))
    return (is_secretariat(user) or
            is_chair_of_draft(user, draft))


def can_edit_stream(user, draft):
    return is_secretariat(user)

def can_adopt(user, draft):
    if settings.USE_DB_REDESIGN_PROXY_CLASSES and draft.stream_id == "ise":
        person = get_person_for_user(user)
        if not person:
            return False
        return is_wgchair(person) or is_wgdelegate(person)
    else:
        return is_secretariat(user)
    
