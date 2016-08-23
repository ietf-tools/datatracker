from itertools import chain

from ietf.group.models import Role
from ietf.liaisons.models import LiaisonStatement
from ietf.ietfauth.utils import has_role, passes_test_decorator

can_submit_liaison_required = passes_test_decorator(
    lambda u, *args, **kwargs: can_add_liaison(u),
    "Restricted to participants who are authorized to submit liaison statements on behalf of the various IETF entities")

def approvable_liaison_statements(user):
    '''Returns a queryset of Liaison Statements in pending state that user has authority
    to approve'''
    liaisons = LiaisonStatement.objects.filter(state__slug__in=('pending','dead'))
    person = get_person_for_user(user)
    if has_role(user, "Secretariat"):
        return liaisons

    approvable_liaisons = []
    for liaison in liaisons:
        for group in liaison.from_groups.all():
            if person not in [ r.person for r in group.liaison_approvers() ]:
                break
        else:
            approvable_liaisons.append(liaison.pk)

    return liaisons.filter(id__in=approvable_liaisons)

def can_edit_liaison(user, liaison):
    '''Returns True if user has edit / approval authority.
    
    True if:
    - user is Secretariat
    - liaison is outgoing and user has approval authority
    - user is liaison manager of all SDOs involved
    '''
    if not user.is_authenticated():
        return False
    if has_role(user, "Secretariat"):
        return True

    if liaison.is_outgoing() and liaison in approvable_liaison_statements(user):
        return True

    if has_role(user, "Liaison Manager"):
        person = get_person_for_user(user)
        for group in chain(liaison.from_groups.filter(type_id='sdo'),liaison.to_groups.filter(type_id='sdo')):
            if not person.role_set.filter(group=group,name='liaiman'):
                return False
        else:
            return True

    return False

def get_person_for_user(user):
    try:
        return user.person
    except:
        return None

def can_add_outgoing_liaison(user):
    return has_role(user, ["Area Director","WG Chair","WG Secretary","IETF Chair","IAB Chair",
        "IAB Executive Director","Liaison Manager","Secretariat"])

def can_add_incoming_liaison(user):
    return has_role(user, ["Liaison Manager","Authorized Individual","Secretariat"])

def can_add_liaison(user):
    return can_add_incoming_liaison(user) or can_add_outgoing_liaison(user)

def is_authorized_individual(user, groups):
    '''Returns True if the user has authorized_individual role for each of the groups'''
    for group in groups:
        if not Role.objects.filter(person=user.person, group=group, name="auth"):
            return False
    return True

