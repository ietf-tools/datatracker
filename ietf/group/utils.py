# Copyright The IETF Trust 2012-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import io
import os

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.safestring import mark_safe
from django.urls import reverse as urlreverse

import debug                            # pyflakes:ignore

from ietf.community.models import CommunityList, SearchRule
from ietf.community.utils import reset_name_contains_index_for_rule, can_manage_community_list
from ietf.doc.models import Document, State
from ietf.group.models import Group, RoleHistory, Role, GroupFeatures
from ietf.ietfauth.utils import has_role
from ietf.name.models import GroupTypeName
from ietf.person.models import Email
from ietf.review.utils import can_manage_review_requests_for_team
from ietf.utils import log
from ietf.utils.history import get_history_object_for, copy_many_to_many_for_history
from functools import reduce

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
        with io.open(filename, 'rb') as f:
            text = f.read()
            try:
                text = text.decode('utf8')
            except UnicodeDecodeError:
                text = text.decode('latin1')
            return text
    except IOError:
        return 'Error Loading Group Charter'

def get_group_role_emails(group, roles):
    "Get a list of email addresses for a given WG and Role"
    if not group or not group.acronym or group.acronym == 'none':
        return set()
    emails = Email.objects.filter(role__group=group, role__name__in=roles)
    return set([_f for _f in [e.email_address() for e in emails] if _f])

def get_child_group_role_emails(parent, roles, group_type='wg'):
    """Get a list of email addresses for a given set of
    roles for all child groups of a given type"""
    emails = set()
    groups = Group.objects.filter(parent=parent, type=group_type, state="active")
    for group in groups:
        emails |= get_group_role_emails(group, roles)
    return emails

def get_group_ad_emails(group):
    " Get list of area directors' email addresses for a given GROUP "
    if not group.acronym or group.acronym == 'none':
        return set()
    if group.type.slug == 'area':
        emails = get_group_role_emails(group, roles=('pre-ad', 'ad', 'chair'))
    else:
        emails = get_group_role_emails(group.parent, roles=('pre-ad', 'ad', 'chair'))
    # Make sure the assigned AD is included (in case that is not one of the area ADs)
    if group.state.slug=='active':
        wg_ad_email = group.ad_role() and group.ad_role().email.address
        if wg_ad_email:
            emails.add(wg_ad_email)
    return emails

def save_milestone_in_history(milestone):
    h = get_history_object_for(milestone)
    h.milestone = milestone
    h.save()

    copy_many_to_many_for_history(h, milestone)

    return h

def can_manage_all_groups_of_type(user, type_id):
    if not user.is_authenticated:
        return False
    log.assertion("isinstance(type_id, (type(''), type(u'')))")
    return has_role(user, GroupFeatures.objects.get(type_id=type_id).groupman_authroles) 

def can_manage_group(user, group):
    if not user.is_authenticated:
        return False
    if has_role(user, group.features.groupman_authroles):
        return True
    return group.has_role(user, group.features.groupman_roles)

def milestone_reviewer_for_group_type(group_type):
    if group_type == "rg":
        return "IRTF Chair"
    else:
        return "Area Director"

def can_manage_materials(user, group):
    return has_role(user, 'Secretariat') or (group is not None and group.has_role(user, group.features.matman_roles))

def can_manage_session_materials(user, group, session):
    return has_role(user, 'Secretariat') or (group.has_role(user, group.features.matman_roles) and not session.is_material_submission_cutoff())

# Maybe this should be cached...
def can_manage_some_groups(user):
    if not user.is_authenticated:
        return False
    for gf in GroupFeatures.objects.all():
        for authrole in gf.groupman_authroles:
            if has_role(user, authrole):
                return True
            if Role.objects.filter(name__in=gf.groupman_roles, group__type_id=gf.type_id, person__user=user).exists():
                return True
    return False          

def can_provide_status_update(user, group):
    if not group.features.acts_like_wg:
        return False
    return has_role(user, 'Secretariat') or group.has_role(user, group.features.groupman_roles)

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
    entries.append(("About", urlreverse("ietf.group.views.group_about", kwargs=kwargs)))
    if group.features.has_documents:
        entries.append(("Documents", urlreverse("ietf.group.views.group_documents", kwargs=kwargs)))
    if group.features.has_nonsession_materials and get_group_materials(group).exists():
        entries.append(("Materials", urlreverse("ietf.group.views.materials", kwargs=kwargs)))
    if group.features.has_reviews:
        import ietf.group.views
        entries.append(("Review requests", urlreverse(ietf.group.views.review_requests, kwargs=kwargs)))
        entries.append(("Reviewers", urlreverse(ietf.group.views.reviewer_overview, kwargs=kwargs)))

    if group.features.has_meetings:
        entries.append(("Meetings", urlreverse("ietf.group.views.meetings", kwargs=kwargs)))
    entries.append(("History", urlreverse("ietf.group.views.history", kwargs=kwargs)))
    entries.append(("Photos", urlreverse("ietf.group.views.group_photos", kwargs=kwargs)))
    entries.append(("Email expansions", urlreverse("ietf.group.views.email", kwargs=kwargs)))
    if group.list_archive.startswith("http:") or group.list_archive.startswith("https:") or group.list_archive.startswith("ftp:"):
        entries.append((mark_safe("List archive &raquo;"), group.list_archive))
    if group.has_tools_page():
        entries.append((mark_safe("Tools &raquo;"), "https://tools.ietf.org/%s/%s/" % (group.type_id, group.acronym)))

    # actions
    actions = []

    can_manage = can_manage_group(request.user, group)
    can_edit_group = False              # we'll set this further down

    if group.features.has_milestones:
        if group.state_id != "proposed" and can_manage:
            actions.append(("Edit milestones", urlreverse('ietf.group.milestones.edit_milestones;current', kwargs=kwargs)))

    if group.features.has_documents:
        clist = CommunityList.objects.filter(group=group).first()
        if clist and can_manage_community_list(request.user, clist):
            import ietf.community.views
            actions.append(('Manage document list', urlreverse(ietf.community.views.manage_list, kwargs=kwargs)))

    if group.features.has_nonsession_materials and can_manage_materials(request.user, group):
        actions.append(("Upload material", urlreverse("ietf.doc.views_material.choose_material_type", kwargs=kwargs)))

    if group.features.has_reviews and can_manage_review_requests_for_team(request.user, group):
        import ietf.group.views
        actions.append(("Manage unassigned reviews", urlreverse(ietf.group.views.manage_review_requests, kwargs=dict(assignment_status="unassigned", **kwargs))))
        #actions.append((u"Manage assigned reviews", urlreverse(ietf.group.views.manage_review_requests, kwargs=dict(assignment_status="assigned", **kwargs))))

        if Role.objects.filter(name="secr", group=group, person__user=request.user).exists():
            actions.append(("Secretary settings", urlreverse(ietf.group.views.change_review_secretary_settings, kwargs=kwargs)))
            actions.append(("Email open assignments summary", urlreverse(ietf.group.views.email_open_review_assignments, kwargs=dict(acronym=group.acronym, group_type=group.type_id))))

    if group.state_id != "conclude" and can_manage:
        can_edit_group = True
        actions.append(("Edit group", urlreverse("ietf.group.views.edit", kwargs=dict(kwargs, action="edit"))))

    if group.features.customize_workflow and can_manage:
        actions.append(("Customize workflow", urlreverse("ietf.group.views.customize_workflow", kwargs=kwargs)))

    if group.state_id in ("active", "dormant") and group.type_id in ["wg", "rg", ] and can_manage_all_groups_of_type(request.user, group.type_id):
        actions.append(("Request closing group", urlreverse("ietf.group.views.conclude", kwargs=kwargs)))

    d = {
        "group": group,
        "selected_menu_entry": selected,
        "menu_entries": entries,
        "menu_actions": actions,
        "group_type": group_type,
        "can_edit_group": can_edit_group,
    }

    d.update(others)

    return d


def group_features_group_filter(groups, person, feature):
    """This returns a list of groups filtered such that the given person has
    a role listed in the given feature for each group."""
    feature_groups = set([])
    for g in groups:
        for r in person.role_set.filter(group=g):
            if r.name.slug in getattr(r.group.type.features, feature):
                feature_groups.add(g)
    return list(feature_groups)

def group_features_role_filter(roles, person, feature):
    type_slugs = set(roles.values_list('group__type__slug', flat=True))
    group_types = GroupTypeName.objects.filter(slug__in=type_slugs)
    if not group_types.exists():
        return roles.none()
    q = reduce(lambda a,b:a|b, [ Q(person=person, name__slug__in=getattr(t.features, feature)) for t in group_types ])
    return roles.filter(q)
    
