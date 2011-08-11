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


def is_delegate_of_stream(user, stream):
    if is_secretariat(user):
        return True
    person = get_person_for_user(user)
    return stream.check_delegate(person)


def is_chair_of_stream(user, stream):
    if is_secretariat(user):
        return True
    person = get_person_for_user(user)
    return stream.check_chair(person)


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
    if chairs and person in chairs:
        return True
    # Check if the person is authorized by a delegate system
    delegates = streamed.stream.get_delegates_for_document(draft)
    return bool(person in delegates)


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
            is_authorized_in_draft_stream(user, draft))


def can_edit_stream(user, draft):
    return is_secretariat(user)
