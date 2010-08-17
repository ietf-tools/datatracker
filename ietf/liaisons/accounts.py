from ietf.idtracker.models import Role, PersonOrOrgInfo


LIAISON_EDIT_GROUPS = ['Liaison_Manager', 'Secretariat']

def get_ietf_chair():
    person = PersonOrOrgInfo.objects.filter(role=Role.IETF_CHAIR)
    return person and person[0] or None


def get_iesg_chair():
    return get_ietf_chair()


def get_iab_chair():
    person = PersonOrOrgInfo.objects.filter(role=Role.IAB_CHAIR)
    return person and person[0] or None


def get_iab_executive_director():
    person = PersonOrOrgInfo.objects.filter(role=Role.IAB_EXCUTIVE_DIRECTOR)
    return person and person[0] or None


def get_person_for_user(user):
    try:
        return user.get_profile().person()
    except:
        return None


def is_areadirector(person):
    return bool(person.areadirector_set.all())


def is_wgchair(person):
    return bool(person.wgchair_set.all())


def is_wgsecretary(person):
    return bool(person.wgsecretary_set.all())


def has_role(person, role):
    return bool(person.role_set.filter(pk=role))


def is_ietfchair(person):
    return has_role(person, Role.IETF_CHAIR)


def is_iabchair(person):
    return has_role(person, Role.IAB_CHAIR)


def is_iab_executive_director(person):
    return has_role(person, Role.IAB_EXCUTIVE_DIRECTOR)


def can_add_outgoing_liaison(user):
    person = get_person_for_user(user)
    if not person:
        return False

    if (is_areadirector(person) or is_wgchair(person) or
        is_wgsecretary(person) or is_ietfchair(person) or
        is_iabchair(person) or is_iab_executive_director(person) or
        is_ietf_liaison_manager(user)):
        return True
    return False


def is_sdo_liaison_manager(person):
    return bool(person.liaisonmanagers_set.all())


def is_sdo_authorized_individual(person):
    return bool(person.sdoauthorizedindividual_set.all())


def is_ietf_liaison_manager(user):
    return bool(user.groups.filter(name='Liaison_Manager'))


def can_add_incoming_liaison(user):
    person = get_person_for_user(user)
    if not person:
        return False

    if (is_sdo_liaison_manager(person) or
        is_sdo_authorized_individual(person) or
        is_ietf_liaison_manager(user)):
        return True
    return False


def can_add_liaison(user):
    return can_add_incoming_liaison(user) or can_add_outgoing_liaison(user)
