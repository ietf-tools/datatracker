from django.conf import settings

from django.db.models import Q

from ietf.ietfworkflows.streams import get_streamed_draft
from ietf.group.models import Role


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

def is_delegate_of_stream(user, stream):
    if is_secretariat(user):
        return True
    person = get_person_for_user(user)
    return stream.check_delegate(person)

def is_delegate_of_streamREDESIGN(user, stream):
    if is_secretariat(user):
        return True
    return user.is_authenticated() and bool(Role.objects.filter(group__acronym=stream.slug, name="delegate", person__user=user))


def is_chair_of_stream(user, stream):
    if is_secretariat(user):
        return True
    person = get_person_for_user(user)
    return stream.check_chair(person)

def is_chair_of_streamREDESIGN(user, stream):
    if is_secretariat(user):
        return True
    if isinstance(user, basestring):
        return False
    return user.is_authenticated() and bool(Role.objects.filter(group__acronym=stream.slug, name="chair", person__user=user))


def is_authorized_in_draft_stream(user, draft):
    if is_secretariat(user):
        return True
    person = get_person_for_user(user)
    if not person:
        return False
    streamed = get_streamed_draft(draft)
    if not streamed or not streamed.stream:
        return False
    # Check if the person is chair of the stream
    if is_chair_of_stream(user, streamed.stream):
        return True
    # Check if the person is delegate of the stream
    if is_delegate_of_stream(user, streamed.stream):
        return True
    # Check if the person is chair of the related group
    chairs = streamed.stream.get_chairs_for_document(draft)
    if chairs and person in [i.person for i in chairs]:
        return True
    # Check if the person is authorized by a delegate system
    delegates = streamed.stream.get_delegates_for_document(draft)
    return bool(person in delegates)

def is_authorized_in_draft_streamREDESIGN(user, draft):
    if is_secretariat(user):
        return True

    from ietf.doc.models import Document

    if not super(Document, draft).stream:
        return False

    # must be a chair or delegate of the stream group (or draft group)
    group_req = Q(group__acronym=super(Document, draft).stream.slug)
    if draft.group and super(Document, draft).stream.slug == "ietf":
        group_req |= Q(group=draft.group)

    return user.is_authenticated() and bool(Role.objects.filter(name__in=("chair", "delegate"), person__user=user).filter(group_req))


if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    from ietf.liaisons.accounts import is_secretariat, get_person_for_user
    is_wgdelegate = is_wgdelegateREDESIGN
    is_wgchair = is_wgchairREDESIGN
    is_chair_of_stream = is_chair_of_streamREDESIGN
    is_delegate_of_stream = is_delegate_of_streamREDESIGN
    is_authorized_in_draft_stream = is_authorized_in_draft_streamREDESIGN


def can_edit_state(user, draft):
    return (is_secretariat(user) or
            is_authorized_in_draft_stream(user, draft))


def can_edit_stream(user, draft):
    return is_secretariat(user)

def can_adopt(user, draft):
    if settings.USE_DB_REDESIGN_PROXY_CLASSES and (not draft.stream_id or draft.stream_id == "ietf") and draft.group.type_id == "individ":
        person = get_person_for_user(user)
        if not person:
            return False
        return is_wgchair(person) or is_wgdelegate(person) or is_secretariat(user)
    else:
        return is_secretariat(user)
    
