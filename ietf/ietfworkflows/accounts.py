from ietf.ietfworkflows.streams import get_streamed_draft


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


def is_wgdelegate(person):
    return bool(person.wgdelegate_set.all())


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


def can_edit_state(user, draft):
    streamed = get_streamed_draft(draft)
    if not streamed or not streamed.stream:
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
