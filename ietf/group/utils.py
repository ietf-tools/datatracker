import os

from django.conf import settings

from ietf.group.models import *
from ietf.utils.history import get_history_object_for, copy_many_to_many_for_history


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
    try:
        # Try getting charter from new charter tool
        c = group.charter

        # find the latest, preferably approved, revision
        for h in group.charter.history_set.exclude(rev="").order_by("time"):
            h_appr = "-" not in h.rev
            c_appr = "-" not in c.rev
            if (h.rev > c.rev and not (c_appr and not h_appr)) or (h_appr and not c_appr):
                c = h

        filename = os.path.join(c.get_file_path(), "%s-%s.txt" % (c.canonical_name(), c.rev))
        with open(filename) as f:
            return f.read()
    except IOError:
        try:
            filename = os.path.join(settings.IETFWG_DESCRIPTIONS_PATH, group.acronym) + ".desc.txt"
            desc_file = open(filename)
            desc = desc_file.read()
        except BaseException:
            desc = 'Error Loading Work Group Description'
        return desc

def get_area_ads_emails(area):
    emails = [r.email.email_address()
              for r in area.role_set.filter(name__in=('ad', 'chair'))]
    return filter(None, emails)

def get_group_ads_emails(wg):
    " Get list of area directors' emails for a given WG "
    if wg.parent:
        # By default, we should use _current_ list of ads!
        return get_area_ads_emails(wg.parent)

    # As fallback, just return the single ad within the wg
    return [wg.ad and wg.ad.email_address()]

def get_group_chairs_emails(wg):
    " Get list of area chairs' emails for a given WG "
    emails = Email.objects.filter(role__group=wg,
                                  role__name='chair')
    if not emails:
        return
    emails = [e.email_address() for e in emails]
    emails = filter(None, emails)
    return emails

def get_area_chairs_emails(area):
    emails = {}
    # XXX - should we filter these by validity? Or not?
    wgs = Group.objects.filter(parent=area, type="wg", state="active")
    for wg in wgs:
        for e in get_group_chairs_emails(wg):
            emails[e] = True
    return emails.keys()

def save_milestone_in_history(milestone):
    h = get_history_object_for(milestone)
    h.milestone = milestone
    h.save()

    copy_many_to_many_for_history(h, milestone)

    return h
