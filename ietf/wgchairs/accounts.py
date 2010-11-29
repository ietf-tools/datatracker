def is_group_chair(person, group):
    if group.chairs().filter(person=person):
        return True
    return False


def get_person_for_user(user):
    try:
        return user.get_profile().person()
    except:
        return None


def can_do_wg_workflow_in_group(user, group):
    person = get_person_for_user(user)
    if not person:
        return False
    return is_group_chair(person, group)


def can_do_wg_workflow_in_document(user, document):
    person = get_person_for_user(user)
    if not person or not document.group:
        return False
    return can_do_wg_workflow_in_group(document.group)


def can_manage_workflow_in_group(user, group):
    person = get_person_for_user(user)
    if not person:
        return False
    return is_group_chair(person, group)


def can_manage_delegates_in_group(user, group):
    person = get_person_for_user(user)
    if not person:
        return False
    return is_group_chair(person, group)
