from django.conf import settings

from ietf.idtracker.models import Role, PersonOrOrgInfo


LIAISON_EDIT_GROUPS = ['Secretariat']


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
        is_sdo_liaison_manager(person) or is_secretariat(user)):
        return True
    return False


def is_sdo_liaison_manager(person):
    return bool(person.liaisonmanagers_set.all())


def is_sdo_authorized_individual(person):
    return bool(person.sdoauthorizedindividual_set.all())


def is_secretariat(user):
    return bool(user.groups.filter(name='Secretariat'))


def can_add_incoming_liaison(user):
    person = get_person_for_user(user)
    if not person:
        return False

    if (is_sdo_liaison_manager(person) or
        is_sdo_authorized_individual(person) or
        is_secretariat(user)):
        return True
    return False


def can_add_liaison(user):
    return can_add_incoming_liaison(user) or can_add_outgoing_liaison(user)


def is_sdo_manager_for_outgoing_liaison(person, liaison):
    from ietf.liaisons.utils import IETFHM, SDOEntity
    from ietf.liaisons.models import SDOs
    from_entity = IETFHM.get_entity_by_key(liaison.from_raw_code)
    sdo = None
    if not from_entity:
        try:
            sdo = SDOs.objects.get(sdo_name=liaison.from_body())
        except SDOs.DoesNotExist:
            pass
    elif isinstance(from_entity, SDOEntity):
        sdo = from_entity.obj
    if sdo:
        return bool(sdo.liaisonmanagers_set.filter(person=person))
    return False


def is_sdo_manager_for_incoming_liaison(person, liaison):
    from ietf.liaisons.utils import IETFHM, SDOEntity
    from ietf.liaisons.models import SDOs
    to_entity = IETFHM.get_entity_by_key(liaison.to_raw_code)
    sdo = None
    if not to_entity:
        try:
            sdo = SDOs.objects.get(sdo_name=liaison.to_body)
        except SDOs.DoesNotExist:
            pass
    elif isinstance(to_entity, SDOEntity):
        sdo = to_entity.obj
    if sdo:
        return bool(sdo.liaisonmanagers_set.filter(person=person))
    return False


def can_edit_liaison(user, liaison):
    if is_secretariat(user):
        return True
    person = get_person_for_user(user)
    if is_sdo_liaison_manager(person):
        return (is_sdo_manager_for_outgoing_liaison(person, liaison) or
                is_sdo_manager_for_incoming_liaison(person, liaison))
    return False

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    from accountsREDESIGN import * 
