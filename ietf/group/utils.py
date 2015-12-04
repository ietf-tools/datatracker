import os

from django.shortcuts import get_object_or_404

import debug                            # pyflakes:ignore

from ietf.group.models import Group, RoleHistory
from ietf.person.models import Email
from ietf.utils.history import get_history_object_for, copy_many_to_many_for_history
from ietf.ietfauth.utils import has_role


def save_group_in_history(group):
    """This should be called before saving changes to a Group instance,
    so that the GroupHistory entries contain all previous states, while
    the Group entry contain the current state.  XXX TODO: Call this
    directly from Group.save()
    """
    h = get_history_object_for(group)
    h.save()

    # save RoleHistory
    for role in group.role_set.all():
        rh = RoleHistory(name=role.name, group=h, email=role.email, person=role.person)
        rh.save()

    copy_many_to_many_for_history(h, group)

    return h

def get_charter_text(group):
    # get file path from settings. Syntesize file name from path, acronym, and suffix
    c = group.charter

    # find the latest, preferably approved, revision
    for h in group.charter.history_set.exclude(rev="").order_by("time"):
        h_appr = "-" not in h.rev
        c_appr = "-" not in c.rev
        if (h.rev > c.rev and not (c_appr and not h_appr)) or (h_appr and not c_appr):
            c = h

    filename = os.path.join(c.get_file_path(), "%s-%s.txt" % (c.canonical_name(), c.rev))
    try:
        with open(filename) as f:
            return f.read()
    except IOError:
        return 'Error Loading Group Charter'

def get_group_role_emails(group, roles):
    "Get a list of email addresses for a given WG and Role"
    if not group or not group.acronym or group.acronym == 'none':
        return set()
    emails = Email.objects.filter(role__group=group, role__name__in=roles)
    return set(filter(None, [e.email_address() for e in emails]))

def get_child_group_role_emails(parent, roles, group_type='wg'):
    """Get a list of email addresses for a given set of
    roles for all child groups of a given type"""
    emails = set()
    groups = Group.objects.filter(parent=parent, type=group_type, state="active")
    for group in groups:
        emails |= get_group_role_emails(group, roles)
    return emails

def get_group_ad_emails(wg):
    " Get list of area directors' email addresses for a given WG "
    if not wg.acronym or wg.acronym == 'none':
        return set()
    emails = get_group_role_emails(wg.parent, roles=('pre-ad', 'ad', 'chair'))
    # Make sure the assigned AD is included (in case that is not one of the area ADs)
    if wg.state.slug=='active':
        wg_ad_email = wg.ad_role() and wg.ad_role().email.address
        if wg_ad_email:
            emails.add(wg_ad_email)
    return emails

def save_milestone_in_history(milestone):
    h = get_history_object_for(milestone)
    h.milestone = milestone
    h.save()

    copy_many_to_many_for_history(h, milestone)

    return h

def can_manage_group_type(user, group_type):
    if group_type == "rg":
        return has_role(user, ('IRTF Chair', 'Secretariat'))
    elif group_type == "wg":
        return has_role(user, ('Area Director', 'Secretariat'))

    return has_role(user, 'Secretariat')

def milestone_reviewer_for_group_type(group_type):
    if group_type == "rg":
        return "IRTF Chair"
    else:
        return "Area Director"

def can_manage_materials(user, group):
    return has_role(user, 'Secretariat') or group.has_role(user, ("chair", "delegate", "secr", "matman"))

def get_group_or_404(acronym, group_type):
    """Helper to overcome the schism between group-type prefixed URLs and generic."""
    possible_groups = Group.objects.all()
    if group_type:
        possible_groups = possible_groups.filter(type=group_type)

    return get_object_or_404(possible_groups, acronym=acronym)
