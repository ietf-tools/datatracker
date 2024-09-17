# Copyright The IETF Trust 2012-2023, All Rights Reserved
# -*- coding: utf-8 -*-
import datetime

from itertools import chain
from pathlib import Path

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.urls import reverse as urlreverse

import debug                            # pyflakes:ignore

from ietf.community.models import CommunityList, SearchRule
from ietf.community.utils import reset_name_contains_index_for_rule, can_manage_community_list
from ietf.doc.models import Document, State, RelatedDocument
from ietf.group.models import Group, RoleHistory, Role, GroupFeatures, GroupEvent
from ietf.ietfauth.utils import has_role
from ietf.name.models import GroupTypeName, RoleName
from ietf.person.models import Email
from ietf.review.utils import can_manage_review_requests_for_team
from ietf.utils import log, markdown
from ietf.utils.history import get_history_object_for, copy_many_to_many_for_history
from ietf.doc.templatetags.ietf_filters import is_valid_url
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

    filename = Path(c.get_file_path()) / f"{c.name}-{c.rev}.txt"
    try:
        text = filename.read_bytes()
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

def groups_managed_by(user, group_queryset=None):
    """Find groups user can manage"""
    if group_queryset is None:
        group_queryset = Group.objects.all()
    query_terms = Q(pk__in=[])  # ensure empty set is returned if no other terms are added
    if user.is_authenticated or user.person:
        # find the GroupTypes entirely managed by this user based on groupman_authroles
        types_can_manage = []
        for type_id, groupman_authroles in GroupFeatures.objects.values_list('type_id', 'groupman_authroles'):
            if has_role(user, groupman_authroles):
                types_can_manage.append(type_id)
        query_terms |= Q(type_id__in=types_can_manage)
        # find the Groups managed by this user based on groupman_roles
        groups_can_manage = []
        for group_id, role_name, groupman_roles in user.person.role_set.values_list(
                'group_id', 'name_id', 'group__type__features__groupman_roles'
        ):
            if role_name in groupman_roles:
                groups_can_manage.append(group_id)
        query_terms |= Q(pk__in=groups_can_manage)
    return group_queryset.filter(query_terms)

def milestone_reviewer_for_group_type(group_type):
    if group_type == "rg":
        return "IRTF Chair"
    else:
        return "Area Director"

def can_manage_materials(user, group):
    return has_role(user, 'Secretariat') or (group is not None and group.has_role(user, group.features.matman_roles))

def can_manage_session_materials(user, group, session):
    return has_role(user, 'Secretariat') or (group.has_role(user, group.features.matman_roles) and not session.is_material_submission_cutoff())

def can_manage_some_groups(user):
    if not user.is_authenticated:
        return False
    authroles = set(
        chain.from_iterable(
            GroupFeatures.objects.values_list("groupman_authroles", flat=True)
        )
    )
    extra_role_qs = dict()
    for gf in GroupFeatures.objects.all():
        extra_role_qs[f"{gf.type_id} groupman roles"] = Q(
            name__in=gf.groupman_roles,
            group__type_id=gf.type_id,
            group__state__in=["active", "bof", "proposed"],
        )
    return has_role(user, authroles, extra_role_qs=extra_role_qs)
       

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
        state=State.objects.get(slug="published", type="rfc"),
    )
    SearchRule.objects.create(
        community_list=clist,
        rule_type="group_exp",
        group=group,
        state=State.objects.get(slug="expired", type="draft"),
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
    if group.acronym in ["iab", "iesg"]:
        entries.append(("Statements", urlreverse("ietf.group.views.statements", kwargs=kwargs)))
        entries.append(("Appeals", urlreverse("ietf.group.views.appeals", kwargs=kwargs)))
    entries.append(("History", urlreverse("ietf.group.views.history", kwargs=kwargs)))
    entries.append(("Photos", urlreverse("ietf.group.views.group_photos", kwargs=kwargs)))
    entries.append(("Email expansions", urlreverse("ietf.group.views.email", kwargs=kwargs)))
    if group.list_archive.startswith("http:") or group.list_archive.startswith("https:") or group.list_archive.startswith("ftp:"):
        if is_valid_url(group.list_archive):
            entries.append((mark_safe("List archive &raquo;"), group.list_archive))


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


def group_attribute_change_desc(attr, new, old=None):
    if old is None:
        return format_html('{} changed to <b>{}</b>', attr, new)
    else:
        return format_html('{} changed to <b>{}</b> from {}', attr, new, old)


def update_role_set(group, role_name, new_value, by):
    """Alter role_set for a group

    Updates the value and creates history events.
    """
    if isinstance(role_name, str):
        role_name = RoleName.objects.get(slug=role_name)
    new = set(new_value)
    old = set(r.email for r in group.role_set.filter(name=role_name).distinct().select_related("person"))
    removed = old - new
    added = new - old
    if added or removed:
        GroupEvent.objects.create(
            group=group,
            by=by,
            type='info_changed',
            desc=group_attribute_change_desc(
                role_name.name,
                ", ".join(sorted(x.get_name() for x in new)),
                ", ".join(sorted(x.get_name() for x in old)),
            )
        )

        group.role_set.filter(name=role_name, email__in=removed).delete()
        for email in added:
            group.role_set.create(name=role_name, email=email, person=email.person)

        for e in new:
            if not e.origin or (e.person.user and e.origin == e.person.user.username):
                e.origin = "role: %s %s" % (group.acronym, role_name.slug)
                e.save()

    return added, removed


class GroupAliasGenerator:
    days = 5 * 365
    active_states = ["active", "bof", "proposed"]
    group_types = [
        "wg",
        "rg",
        "rag",
        "dir",
        "team",
        "review",
        "program",
        "rfcedtyp",
        "edappr",
        "edwg",
    ]  # This should become groupfeature driven...
    no_ad_group_types = ["rg", "rag", "team", "program", "rfcedtyp", "edappr", "edwg"]

    def __init__(self, group_queryset=None):
        if group_queryset is None:
            self.group_queryset = Group.objects.all()
        else:
            self.group_queryset = group_queryset

    def __iter__(self):
        show_since = timezone.now() - datetime.timedelta(days=self.days)

        # Loop through each group type and build -ads and -chairs entries
        for g in self.group_types:
            domains = ["ietf"]
            if g in ("rg", "rag"):
                domains.append("irtf")
            if g == "program":
                domains.append("iab")

            entries = self.group_queryset.filter(type=g).all()
            active_entries = entries.filter(state__in=self.active_states)
            inactive_recent_entries = entries.exclude(
                state__in=self.active_states
            ).filter(time__gte=show_since)
            interesting_entries = active_entries | inactive_recent_entries

            for e in interesting_entries.distinct().iterator():
                name = e.acronym

                # Research groups, teams, and programs do not have -ads lists
                if not g in self.no_ad_group_types:
                    ad_emails = get_group_ad_emails(e)
                    if ad_emails:
                        yield name + "-ads", domains, list(ad_emails)
                # All group types have -chairs lists
                chair_emails = get_group_role_emails(e, ["chair", "secr"])
                if chair_emails:
                    yield name + "-chairs", domains, list(chair_emails)

        # The area lists include every chair in active working groups in the area
        areas = self.group_queryset.filter(type="area").all()
        active_areas = areas.filter(state__in=self.active_states)
        for area in active_areas:
            name = area.acronym
            area_ad_emails = get_group_role_emails(area, ["pre-ad", "ad", "chair"])
            if area_ad_emails:
                yield name + "-ads", ["ietf"], list(area_ad_emails)
            chair_emails = get_child_group_role_emails(area, ["chair", "secr"]) | area_ad_emails
            if chair_emails:
                yield name + "-chairs", ["ietf"], list(chair_emails)

        # Other groups with chairs that require Internet-Draft submission approval
        gtypes = GroupTypeName.objects.values_list("slug", flat=True)
        special_groups = self.group_queryset.filter(
            type__features__req_subm_approval=True, acronym__in=gtypes, state="active"
        )
        for group in special_groups:
            chair_emails = get_group_role_emails(group, ["chair", "delegate"])
            if chair_emails:
                yield group.acronym + "-chairs", ["ietf"], list(chair_emails)


def get_group_email_aliases(acronym, group_type):
    aliases = []
    group_queryset = Group.objects.all()
    if acronym:
        group_queryset = group_queryset.filter(acronym=acronym)
    if group_type:
        group_queryset = group_queryset.filter(type__slug=group_type)
    for (alias, _, alist) in GroupAliasGenerator(group_queryset):
        acro, _hyphen, alias_type = alias.partition("-")
        expansion = ", ".join(sorted(alist))
        aliases.append({
            "acronym": acro,
            "alias_type": f"-{alias_type}" if alias_type else "",
            "expansion": expansion,
        })
    return sorted(aliases, key=lambda a: a["acronym"])


def role_holder_emails():
    """Get queryset of active Emails for group role holders"""
    group_types_of_interest = [
        "ag",
        "area",
        "dir",
        "iab",
        "ietf",
        "irtf",
        "nomcom",
        "rg",
        "team",
        "wg",
        "rag",
    ]
    roles = Role.objects.filter(
        group__state__slug="active",
        group__type__in=group_types_of_interest,
    )
    emails = Email.objects.filter(active=True).exclude(
        address__startswith="unknown-email-"
    )
    return emails.filter(person__role__in=roles).distinct()


def fill_in_charter_info(group, include_drafts=False):
    group.areadirector = getattr(group.ad_role(),'email',None)

    personnel = {}
    for r in Role.objects.filter(group=group).order_by('person__name').select_related("email", "person", "name"):
        if r.name_id not in personnel:
            personnel[r.name_id] = []
        personnel[r.name_id].append(r)

    if group.parent and group.parent.type_id == "area" and group.ad_role() and "ad" not in personnel:
        ad_roles = list(Role.objects.filter(group=group.parent, name="ad", person=group.ad_role().person))
        if ad_roles:
            personnel["ad"] = ad_roles

    group.personnel = []
    for role_name_slug, roles in personnel.items():
        label = roles[0].name.name
        if len(roles) > 1:
            if label.endswith("y"):
                label = label[:-1] + "ies"
            else:
                label += "s"

        group.personnel.append((role_name_slug, label, roles))

    group.personnel.sort(key=lambda t: t[2][0].name.order)

    milestone_state = "charter" if group.state_id == "proposed" else "active"
    group.milestones = group.groupmilestone_set.filter(state=milestone_state)
    if group.uses_milestone_dates:
        group.milestones = group.milestones.order_by('resolved', 'due')
    else:
        group.milestones = group.milestones.order_by('resolved', 'order')

    if group.charter:
        group.charter_text = get_charter_text(group)
    else:
        group.charter_text = "Not chartered yet."
    group.charter_html = markdown.markdown(group.charter_text)


def fill_in_wg_roles(group):
    def get_roles(slug, default):
        for role_slug, label, roles in group.personnel:
            if slug == role_slug:
                return roles
        return default

    group.chairs = get_roles("chair", [])
    ads = get_roles("ad", [])
    group.areadirector = ads[0] if ads else None
    group.techadvisors = get_roles("techadv", [])
    group.editors = get_roles("editor", [])
    group.secretaries = get_roles("secr", [])


def fill_in_wg_drafts(group):
    group.drafts = Document.objects.filter(type_id="draft", group=group).order_by("name")
    group.rfcs = Document.objects.filter(type_id="rfc", group=group).order_by("rfc_number")
    for rfc in group.rfcs:
        # TODO: remote_field?
        rfc.remote_field = RelatedDocument.objects.filter(source=rfc,relationship_id__in=['obs','updates']).distinct()
        rfc.invrel = RelatedDocument.objects.filter(target=rfc,relationship_id__in=['obs','updates']).distinct()
