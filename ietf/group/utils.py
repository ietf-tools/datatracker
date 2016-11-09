import os

from django.shortcuts import get_object_or_404
from django.utils.safestring import mark_safe
from django.core.urlresolvers import reverse as urlreverse

import debug                            # pyflakes:ignore

from ietf.group.models import Group, RoleHistory, Role
from ietf.person.models import Email
from ietf.utils.history import get_history_object_for, copy_many_to_many_for_history
from ietf.ietfauth.utils import has_role
from ietf.community.models import CommunityList, SearchRule
from ietf.community.utils import reset_name_contains_index_for_rule, can_manage_community_list
from ietf.doc.models import Document, State
from ietf.review.utils import can_manage_review_requests_for_team


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

def can_manage_group(user, group):
    if group.type_id == "rg":
        return has_role(user, ('IRTF Chair', 'Secretariat'))
    elif group.type_id == "wg":
        return has_role(user, ('Area Director', 'Secretariat'))
    elif group.type_id == "team":
        if group.is_decendant_of("ietf"):
            return has_role(user, ('Area Director', 'Secretariat'))
        elif group.is_decendant_of("irtf"):
            return has_role(user, ('IRTF Chair', 'Secretariat'))
    return has_role(user, ('Secretariat'))

def milestone_reviewer_for_group_type(group_type):
    if group_type == "rg":
        return "IRTF Chair"
    else:
        return "Area Director"

def can_manage_materials(user, group):
    return has_role(user, 'Secretariat') or group.has_role(user, ("chair", "delegate", "secr", "matman"))

def can_provide_status_update(user, group):
    if not group.type_id in ['wg','rg','team']:
        return False
    return has_role(user, 'Secretariat') or group.has_role(user, ("chair", "delegate", "secr", "ad",))

def get_group_or_404(acronym, group_type):
    """Helper to overcome the schism between group-type prefixed URLs and generic."""
    possible_groups = Group.objects.all()
    if group_type:
        possible_groups = possible_groups.filter(type=group_type)

    return get_object_or_404(possible_groups, acronym=acronym)

def setup_default_community_list_for_group(group):
    clist = CommunityList.objects.create(group=group)
    SearchRule.objects.create(
        community_list=clist,
        rule_type="group",
        group=group,
        state=State.objects.get(slug="active", type="draft"),
    )
    SearchRule.objects.create(
        community_list=clist,
        rule_type="group_rfc",
        group=group,
        state=State.objects.get(slug="rfc", type="draft"),
    )
    related_docs_rule = SearchRule.objects.create(
        community_list=clist,
        rule_type="name_contains",
        text=r"^draft-[^-]+-%s-" % group.acronym,
        state=State.objects.get(slug="active", type="draft"),
    )
    reset_name_contains_index_for_rule(related_docs_rule)

def get_group_materials(group):
    return Document.objects.filter(
        group=group,
        type__in=group.features.material_types
    ).exclude(states__slug__in=['deleted','archived'])

def construct_group_menu_context(request, group, selected, group_type, others):
    """Return context with info for the group menu filled in."""
    kwargs = dict(acronym=group.acronym)
    if group_type:
        kwargs["group_type"] = group_type

    # menu entries
    entries = []
    if group.features.has_documents:
        entries.append(("Documents", urlreverse("ietf.group.views.group_documents", kwargs=kwargs)))
    if group.features.has_chartering_process:
        entries.append(("Charter", urlreverse("group_charter", kwargs=kwargs)))
    else:
        entries.append(("About", urlreverse("group_about", kwargs=kwargs)))
    if group.features.has_materials and get_group_materials(group).exists():
        entries.append(("Materials", urlreverse("ietf.group.views.materials", kwargs=kwargs)))
    if group.features.has_reviews:
        import ietf.group.views_review
        entries.append(("Review requests", urlreverse(ietf.group.views_review.review_requests, kwargs=kwargs)))
        entries.append(("Reviewers", urlreverse(ietf.group.views_review.reviewer_overview, kwargs=kwargs)))
    if group.type_id in ('rg','wg','team'):
        entries.append(("Meetings", urlreverse("ietf.group.views.meetings", kwargs=kwargs)))
    entries.append(("History", urlreverse("ietf.group.views.history", kwargs=kwargs)))
    entries.append(("Photos", urlreverse("ietf.group.views.group_photos", kwargs=kwargs)))
    entries.append(("Email expansions", urlreverse("ietf.group.views.email", kwargs=kwargs)))
    if group.list_archive.startswith("http:") or group.list_archive.startswith("https:") or group.list_archive.startswith("ftp:"):
        if 'mailarchive.ietf.org' in group.list_archive:
            entries.append(("List archive", urlreverse("ietf.group.views.derived_archives", kwargs=kwargs)))
        else:
            entries.append((mark_safe("List archive &raquo;"), group.list_archive))
    if group.has_tools_page():
        entries.append((mark_safe("Tools &raquo;"), "https://tools.ietf.org/%s/%s/" % (group.type_id, group.acronym)))

    # actions
    actions = []

    is_admin = group.has_role(request.user, group.features.admin_roles)
    can_manage = can_manage_group(request.user, group)

    if group.features.has_milestones:
        if group.state_id != "proposed" and (is_admin or can_manage):
            actions.append((u"Edit milestones", urlreverse("group_edit_milestones", kwargs=kwargs)))

    if group.features.has_documents:
        clist = CommunityList.objects.filter(group=group).first()
        if clist and can_manage_community_list(request.user, clist):
            import ietf.community.views
            actions.append((u'Manage document list', urlreverse(ietf.community.views.manage_list, kwargs=kwargs)))

    if group.features.has_materials and can_manage_materials(request.user, group):
        actions.append((u"Upload material", urlreverse("ietf.doc.views_material.choose_material_type", kwargs=kwargs)))

    if group.features.has_reviews and can_manage_review_requests_for_team(request.user, group):
        import ietf.group.views_review
        actions.append((u"Manage unassigned reviews", urlreverse(ietf.group.views_review.manage_review_requests, kwargs=dict(assignment_status="unassigned", **kwargs))))
        actions.append((u"Manage assigned reviews", urlreverse(ietf.group.views_review.manage_review_requests, kwargs=dict(assignment_status="assigned", **kwargs))))

        if Role.objects.filter(name="secr", group=group, person__user=request.user).exists():
            actions.append((u"Secretary settings", urlreverse(ietf.group.views_review.change_review_secretary_settings, kwargs=kwargs)))


    if group.state_id != "conclude" and (is_admin or can_manage):
        actions.append((u"Edit group", urlreverse("group_edit", kwargs=kwargs)))

    if group.features.customize_workflow and (is_admin or can_manage):
        actions.append((u"Customize workflow", urlreverse("ietf.group.views_edit.customize_workflow", kwargs=kwargs)))

    if group.state_id in ("active", "dormant") and not group.type_id in ["sdo", "rfcedtyp", "isoc", ] and can_manage:
        actions.append((u"Request closing group", urlreverse("ietf.group.views_edit.conclude", kwargs=kwargs)))

    d = {
        "group": group,
        "selected_menu_entry": selected,
        "menu_entries": entries,
        "menu_actions": actions,
        "group_type": group_type,
    }

    d.update(others)

    return d
