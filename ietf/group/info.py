

# Portion Copyright (C) 2010 Nokia Corporation and/or its subsidiary(-ies).
# All rights reserved. Contact: Pasi Eronen <pasi.eronen@nokia.com>
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions 
# are met:
# 
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
# 
#  * Neither the name of the Nokia Corporation and/or its
#    subsidiary(-ies) nor the names of its contributors may be used
#    to endorse or promote products derived from this software
#    without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import os
import itertools
import re
from tempfile import mkstemp
from collections import OrderedDict

from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.conf import settings
from django.core.urlresolvers import reverse as urlreverse
from django.views.decorators.cache import cache_page
from django.db.models import Q
from django.utils.safestring import mark_safe

from ietf.doc.views_search import SearchForm, retrieve_search_results, get_doc_is_tracked
from ietf.doc.models import Document, State, DocAlias, RelatedDocument
from ietf.doc.utils import get_chartering_type
from ietf.doc.templatetags.ietf_filters import clean_whitespace
from ietf.group.models import Group, Role, ChangeStateGroupEvent
from ietf.name.models import GroupTypeName
from ietf.group.utils import get_charter_text, can_manage_group_type, milestone_reviewer_for_group_type
from ietf.group.utils import can_manage_materials, get_group_or_404
from ietf.utils.pipe import pipe
from ietf.settings import MAILING_LIST_INFO_URL
from ietf.mailtrigger.utils import gather_relevant_expansions

def roles(group, role_name):
    return Role.objects.filter(group=group, name=role_name).select_related("email", "person")

def fill_in_charter_info(group, include_drafts=False):
    group.areadirector = getattr(group.ad_role(),'email',None)

    personnel = {}
    for r in Role.objects.filter(group=group).select_related("email", "person", "name"):
        if r.name_id not in personnel:
            personnel[r.name_id] = []
        personnel[r.name_id].append(r)

    if group.parent and group.parent.type_id == "area" and group.ad_role() and "ad" not in personnel:
        ad_roles = list(Role.objects.filter(group=group.parent, name="ad", person=group.ad_role().person))
        if ad_roles:
            personnel["ad"] = ad_roles

    group.personnel = []
    for role_name_slug, roles in personnel.iteritems():
        label = roles[0].name.name
        if len(roles) > 1:
            if label.endswith("y"):
                label = label[:-1] + "ies"
            else:
                label += "s"

        group.personnel.append((role_name_slug, label, roles))

    group.personnel.sort(key=lambda t: t[2][0].name.order)

    milestone_state = "charter" if group.state_id == "proposed" else "active"
    group.milestones = group.groupmilestone_set.filter(state=milestone_state).order_by('due')

    if group.charter:
        group.charter_text = get_charter_text(group)
    else:
        group.charter_text = u"Not chartered yet."

def extract_last_name(role):
    return role.person.name_parts()[3]

def wg_summary_area(request, group_type):
    if group_type != "wg":
        raise Http404
    areas = Group.objects.filter(type="area", state="active").order_by("name")
    for area in areas:
        area.ads = sorted(roles(area, "ad"), key=extract_last_name)
        area.groups = Group.objects.filter(parent=area, type="wg", state="active").order_by("acronym")
        for group in area.groups:
            group.chairs = sorted(roles(group, "chair"), key=extract_last_name)

    areas = [a for a in areas if a.groups]

    return render(request, 'group/1wg-summary.txt',
                  { 'areas': areas },
                  content_type='text/plain; charset=UTF-8')

def wg_summary_acronym(request, group_type):
    if group_type != "wg":
        raise Http404
    areas = Group.objects.filter(type="area", state="active").order_by("name")
    groups = Group.objects.filter(type="wg", state="active").order_by("acronym").select_related("parent")
    for group in groups:
        group.chairs = sorted(roles(group, "chair"), key=extract_last_name)
    return render(request, 'group/1wg-summary-by-acronym.txt',
                  { 'areas': areas,
                    'groups': groups },
                  content_type='text/plain; charset=UTF-8')

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
    aliases = DocAlias.objects.filter(document__type="draft", document__group=group).select_related('document').order_by("name")
    group.drafts = []
    group.rfcs = []
    for a in aliases:
        if a.name.startswith("draft"):
            group.drafts.append(a)
        else:
            group.rfcs.append(a)
            a.rel = RelatedDocument.objects.filter(source=a.document).distinct()
            a.invrel = RelatedDocument.objects.filter(target=a).distinct()

@cache_page ( 60 * 60 )
def wg_charters(request, group_type):
    if group_type != "wg":
        raise Http404
    areas = Group.objects.filter(type="area", state="active").order_by("name")
    for area in areas:
        area.ads = sorted(roles(area, "ad"), key=extract_last_name)
        area.groups = Group.objects.filter(parent=area, type="wg", state="active").order_by("name")
        for group in area.groups:
            fill_in_charter_info(group)
            fill_in_wg_roles(group)
            fill_in_wg_drafts(group)
            group.area = area
    return render(request, 'group/1wg-charters.txt',
                  { 'areas': areas },
                  content_type='text/plain; charset=UTF-8')

@cache_page ( 60 * 60 )
def wg_charters_by_acronym(request, group_type):
    if group_type != "wg":
        raise Http404
    areas = dict((a.id, a) for a in Group.objects.filter(type="area", state="active").order_by("name"))

    for area in areas.itervalues():
        area.ads = sorted(roles(area, "ad"), key=extract_last_name)

    groups = Group.objects.filter(type="wg", state="active").exclude(parent=None).order_by("acronym")
    for group in groups:
        fill_in_charter_info(group)
        fill_in_wg_roles(group)
        fill_in_wg_drafts(group)
        group.area = areas.get(group.parent_id)
    return render(request, 'group/1wg-charters-by-acronym.txt',
                  { 'groups': groups },
                  content_type='text/plain; charset=UTF-8')

def active_groups(request, group_type=None):

    if not group_type:
        return active_group_types(request)
    elif group_type == "wg":
        return active_wgs(request)
    elif group_type == "rg":
        return active_rgs(request)
    elif group_type == "ag":
        return active_ags(request)
    elif group_type == "area":
        return active_areas(request)
    elif group_type == "team":
        return active_teams(request)
    elif group_type == "dir":
        return active_dirs(request)
    else:
        raise Http404

def active_group_types(request):
    grouptypes = GroupTypeName.objects.filter(slug__in=['wg','rg','ag','team','dir','area'])
    return render(request, 'group/active_groups.html', {'grouptypes':grouptypes})

def active_dirs(request):
    dirs = Group.objects.filter(type="dir", state="active").order_by("name")
    for group in dirs:
        group.chairs = sorted(roles(group, "chair"), key=extract_last_name)
        group.ads = sorted(roles(group, "ad"), key=extract_last_name)
        group.secretaries = sorted(roles(group, "secr"), key=extract_last_name)
    return render(request, 'group/active_dirs.html', {'dirs' : dirs })

def active_teams(request):
    teams = Group.objects.filter(type="team", state="active").order_by("name")
    for group in teams:
        group.chairs = sorted(roles(group, "chair"), key=extract_last_name)
    return render(request, 'group/active_teams.html', {'teams' : teams })

def active_areas(request):
	areas = Group.objects.filter(type="area", state="active").order_by("name")  
	return render(request, 'group/active_areas.html', {'areas': areas })

def active_wgs(request):
    areas = Group.objects.filter(type="area", state="active").order_by("name")
    for area in areas:
        # dig out information for template
        area.ads = (list(sorted(roles(area, "ad"), key=extract_last_name))
                    + list(sorted(roles(area, "pre-ad"), key=extract_last_name)))

        area.groups = Group.objects.filter(parent=area, type="wg", state="active").order_by("acronym")
        area.urls = area.groupurl_set.all().order_by("name")
        for group in area.groups:
            group.chairs = sorted(roles(group, "chair"), key=extract_last_name)
            group.ad_out_of_area = group.ad_role() and group.ad_role().person not in [role.person for role in area.ads]
            # get the url for mailing list subscription
            if group.list_subscribe.startswith('http'):
                group.list_subscribe_url = group.list_subscribe
            elif group.list_email.endswith('@ietf.org'):
                group.list_subscribe_url = MAILING_LIST_INFO_URL % {'list_addr':group.list_email.split('@')[0]}
            else:
                group.list_subscribe_url = "mailto:"+group.list_subscribe

    return render(request, 'group/active_wgs.html', { 'areas':areas })

def active_rgs(request):
    irtf = Group.objects.get(acronym="irtf")
    irtf.chair = roles(irtf, "chair").first()

    groups = Group.objects.filter(type="rg", state="active").order_by("acronym")
    for group in groups:
        group.chairs = sorted(roles(group, "chair"), key=extract_last_name)

    return render(request, 'group/active_rgs.html', { 'irtf': irtf, 'groups': groups })
    
def active_ags(request):

    groups = Group.objects.filter(type="ag", state="active").order_by("acronym")
    for group in groups:
        group.chairs = sorted(roles(group, "chair"), key=extract_last_name)
        group.ads = sorted(roles(group, "ad"), key=extract_last_name)

    return render(request, 'group/active_ags.html', { 'groups': groups })
    
def bofs(request, group_type):
    groups = Group.objects.filter(type=group_type, state="bof")
    return render(request, 'group/bofs.html',dict(groups=groups))

def chartering_groups(request):
    charter_states = State.objects.filter(used=True, type="charter").exclude(slug__in=("approved", "notrev"))

    group_types = GroupTypeName.objects.filter(slug__in=("wg", "rg"))

    for t in group_types:
        t.chartering_groups = Group.objects.filter(type=t, charter__states__in=charter_states).select_related("state", "charter").order_by("acronym")
        t.can_manage = can_manage_group_type(request.user, t.slug)

        for g in t.chartering_groups:
            g.chartering_type = get_chartering_type(g.charter)

    return render(request, 'group/chartering_groups.html',
                  dict(charter_states=charter_states,
                       group_types=group_types))

def concluded_groups(request):
    group_types = GroupTypeName.objects.filter(slug__in=("wg", "rg"))

    for t in group_types:
        t.concluded_groups = Group.objects.filter(type=t, state__in=("conclude", "bof-conc")).select_related("state", "charter").order_by("acronym")

        # add start/conclusion date
        d = dict((g.pk, g) for g in t.concluded_groups)

        for g in t.concluded_groups:
            g.start_date = g.conclude_date = None

        for e in ChangeStateGroupEvent.objects.filter(group__in=t.concluded_groups, state="active").order_by("-time"):
            d[e.group_id].start_date = e.time

        for e in ChangeStateGroupEvent.objects.filter(group__in=t.concluded_groups, state="conclude").order_by("time"):
            d[e.group_id].conclude_date = e.time

    return render(request, 'group/concluded_groups.html',
                  dict(group_types=group_types))

def get_group_materials(group):
#   return Document.objects.filter(group=group, type__in=group.features.material_types, session=None).exclude(states__slug="deleted")
    return Document.objects.filter(group=group, type__in=group.features.material_types).exclude(states__slug__in=['deleted','archived'])

def construct_group_menu_context(request, group, selected, group_type, others):
    """Return context with info for the group menu filled in."""
    kwargs = dict(acronym=group.acronym)
    if group_type:
        kwargs["group_type"] = group_type

    # menu entries
    entries = []
    if group.features.has_documents:
        entries.append(("Documents", urlreverse("ietf.group.info.group_documents", kwargs=kwargs)))
    if group.features.has_chartering_process:
        entries.append(("Charter", urlreverse("group_charter", kwargs=kwargs)))
    else:
        entries.append(("About", urlreverse("group_about", kwargs=kwargs)))
    if group.features.has_materials and get_group_materials(group).exists():
        entries.append(("Materials", urlreverse("ietf.group.info.materials", kwargs=kwargs)))
    entries.append(("Email expansions", urlreverse("ietf.group.info.email", kwargs=kwargs)))
    entries.append(("History", urlreverse("ietf.group.info.history", kwargs=kwargs)))
    if group.features.has_documents:
        entries.append((mark_safe("Dependency graph &raquo;"), urlreverse("ietf.group.info.dependencies_pdf", kwargs=kwargs)))

    if group.list_archive.startswith("http:") or group.list_archive.startswith("https:") or group.list_archive.startswith("ftp:"):
        entries.append((mark_safe("List archive &raquo;"), group.list_archive))
    if group.has_tools_page():
        entries.append((mark_safe("Tools page &raquo;"), "https://tools.ietf.org/%s/%s/" % (group.type_id, group.acronym)))


    # actions
    actions = []

    is_chair = group.has_role(request.user, "chair")
    can_manage = can_manage_group_type(request.user, group.type_id)

    if group.features.has_milestones:
        if group.state_id != "proposed" and (is_chair or can_manage):
            actions.append((u"Edit milestones", urlreverse("group_edit_milestones", kwargs=kwargs)))

    if group.features.has_materials and can_manage_materials(request.user, group):
        actions.append((u"Upload material", urlreverse("ietf.doc.views_material.choose_material_type", kwargs=kwargs)))

    if group.type_id in ("rg", "wg") and group.state_id != "conclude" and can_manage:
        actions.append((u"Edit group", urlreverse("group_edit", kwargs=kwargs)))

    if group.features.customize_workflow and (is_chair or can_manage):
        actions.append((u"Customize workflow", urlreverse("ietf.group.edit.customize_workflow", kwargs=kwargs)))

    if group.state_id in ("active", "dormant") and not group.type_id in ["sdo", "rfcedtyp", "isoc", ] and can_manage:
        actions.append((u"Request closing group", urlreverse("ietf.group.edit.conclude", kwargs=kwargs)))

    d = {
        "group": group,
        "selected_menu_entry": selected,
        "menu_entries": entries,
        "menu_actions": actions,
        "group_type": group_type,
        }

    d.update(others)

    return d

def search_for_group_documents(group):
    form = SearchForm({ 'by':'group', 'group': group.acronym or "", 'rfcs':'on', 'activedrafts': 'on' })
    docs, meta = retrieve_search_results(form)

    # get the related docs
    form_related = SearchForm({ 'by':'group', 'name': u'-%s-' % group.acronym, 'activedrafts': 'on' })
    raw_docs_related, meta_related = retrieve_search_results(form_related)

    docs_related = []
    for d in raw_docs_related:
        parts = d.name.split("-", 2);
        # canonical form draft-<name|ietf|irtf>-wg-etc
        if len(parts) >= 3 and parts[1] not in ("ietf", "irtf") and parts[2].startswith(group.acronym + "-"):
            d.search_heading = "Related Internet-Draft"
            docs_related.append(d)

    # move call for WG adoption to related
    cleaned_docs = []
    docs_related_names = set(d.name for d in docs_related)
    for d in docs:
        if d.stream_id and d.get_state_slug("draft-stream-%s" % d.stream_id) in ("c-adopt", "wg-cand"):
            if d.name not in docs_related_names:
                d.search_heading = "Related Internet-Draft"
                docs_related.append(d)
        else:
            cleaned_docs.append(d)

    docs = cleaned_docs

    docs_related.sort(key=lambda d: d.name)

    return docs, meta, docs_related, meta_related

def group_home(request, acronym, group_type=None):
    group = get_group_or_404(acronym, group_type)
    kwargs = dict(acronym=group.acronym)
    if group_type:
        kwargs["group_type"] = group_type
    return HttpResponseRedirect(urlreverse(group.features.default_tab, kwargs=kwargs))

def group_documents(request, acronym, group_type=None):
    group = get_group_or_404(acronym, group_type)
    if not group.features.has_documents:
        raise Http404

    docs, meta, docs_related, meta_related = search_for_group_documents(group)

    doc_is_tracked = get_doc_is_tracked(request, docs)
    doc_is_tracked.update(get_doc_is_tracked(request, docs_related))

    context = construct_group_menu_context(request, group, "documents", group_type, {
                'docs': docs,
                'meta': meta,
                'docs_related': docs_related,
                'meta_related': meta_related,
                'doc_is_tracked': doc_is_tracked,
                })

    return render(request, 'group/group_documents.html', context)

def group_documents_txt(request, acronym, group_type=None):
    """Return tabulator-separated rows with documents for group."""
    group = get_group_or_404(acronym, group_type)
    if not group.features.has_documents:
        raise Http404

    docs, meta, docs_related, meta_related = search_for_group_documents(group)

    for d in docs:
        d.prefix = d.get_state().name

    for d in docs_related:
        d.prefix = u"Related %s" % d.get_state().name

    rows = []
    for d in itertools.chain(docs, docs_related):
        rfc_number = d.rfc_number()
        if rfc_number != None:
            name = rfc_number
        else:
            name = "%s-%s" % (d.name, d.rev)

        rows.append(u"\t".join((d.prefix, name, clean_whitespace(d.title))))

    return HttpResponse(u"\n".join(rows), content_type='text/plain; charset=UTF-8')

def group_about(request, acronym, group_type=None):
    group = get_group_or_404(acronym, group_type)

    fill_in_charter_info(group)

    e = group.latest_event(type__in=("changed_state", "requested_close",))
    requested_close = group.state_id != "conclude" and e and e.type == "requested_close"

    can_manage = can_manage_group_type(request.user, group.type_id)

    return render(request, 'group/group_about.html',
                  construct_group_menu_context(request, group, "charter" if group.features.has_chartering_process else "about", group_type, {
                      "milestones_in_review": group.groupmilestone_set.filter(state="review"),
                      "milestone_reviewer": milestone_reviewer_for_group_type(group_type),
                      "requested_close": requested_close,
                      "can_manage": can_manage,
                  }))

def get_email_aliases(acronym, group_type):
    if acronym:
        pattern = re.compile('expand-(%s)(-\w+)@.*? +(.*)$'%acronym)
    else:
        pattern = re.compile('expand-(.*?)(-\w+)@.*? +(.*)$')

    aliases = []
    with open(settings.GROUP_VIRTUAL_PATH,"r") as virtual_file:
        for line in virtual_file.readlines():
            m = pattern.match(line)
            if m:
                if acronym or not group_type or Group.objects.filter(acronym=m.group(1),type__slug=group_type):
                    aliases.append({'acronym':m.group(1),'alias_type':m.group(2),'expansion':m.group(3)})
    return aliases

def email(request, acronym, group_type=None):
    group = get_group_or_404(acronym, group_type)

    aliases = get_email_aliases(acronym, group_type)
    expansions = gather_relevant_expansions(group=group)

    return render(request, 'group/email.html',
                  construct_group_menu_context(request, group, "email expansions", group_type, {
                       'expansions':expansions,
                       'aliases':aliases,
                       'group':group,
                       'ietf_domain':settings.IETF_DOMAIN,
                  })) 

def history(request, acronym, group_type=None):
    group = get_group_or_404(acronym, group_type)

    events = group.groupevent_set.all().select_related('by').order_by('-time', '-id')

    return render(request, 'group/history.html',
                  construct_group_menu_context(request, group, "history", group_type, {
                      "events": events,
                  }))

def materials(request, acronym, group_type=None):
    group = get_group_or_404(acronym, group_type)
    if not group.features.has_materials:
        raise Http404

    docs = get_group_materials(group).order_by("type__order", "-time").select_related("type")
    doc_types = OrderedDict()
    for d in docs:
        if d.type not in doc_types:
            doc_types[d.type] = []
        doc_types[d.type].append(d)

    return render(request, 'group/materials.html',
                  construct_group_menu_context(request, group, "materials", group_type, {
                      "doc_types": doc_types.items(),
                      "can_manage_materials": can_manage_materials(request.user, group)
                  }))

def nodename(name):
    return name.replace('-','_')

class Edge(object):
    def __init__(self,relateddocument):
        self.relateddocument=relateddocument

    def __hash__(self):
        return hash("|".join([str(hash(nodename(self.relateddocument.source.name))),
                             str(hash(nodename(self.relateddocument.target.document.name))),
                             self.relateddocument.relationship.slug]))

    def __eq__(self,other):
        return self.__hash__() == other.__hash__()

    def sourcename(self):
        return nodename(self.relateddocument.source.name)

    def targetname(self):
        return nodename(self.relateddocument.target.document.name)

    def styles(self):

        # Note that the old style=dotted, color=red styling is never used

        if self.relateddocument.is_downref():
            return { 'color':'red','arrowhead':'normalnormal' }
        else:
            styles = { 'refnorm' : { 'color':'blue'   },
                       'refinfo' : { 'color':'green'  },
                       'refold'  : { 'color':'orange' },
                       'refunk'  : { 'style':'dashed' },
                       'replaces': { 'color':'pink', 'style':'dashed', 'arrowhead':'diamond' },
                     }
            return styles[self.relateddocument.relationship.slug]

def get_node_styles(node,group):

    styles=dict()

    # Shape and style (note that old diamond shape is never used

    styles['style'] = 'filled'

    if node.get_state('draft').slug == 'rfc':
       styles['shape'] = 'box'
    elif node.get_state('draft-iesg') and not node.get_state('draft-iesg').slug in ['watching','dead']:
       styles['shape'] = 'parallelogram'
    elif node.get_state('draft').slug == 'expired':
       styles['shape'] = 'house'
       styles['style'] ='solid'
       styles['peripheries'] = 3
    elif node.get_state('draft').slug == 'repl':
       styles['shape'] = 'ellipse'
       styles['style'] ='solid'
       styles['peripheries'] = 3
    else:
       pass # quieter form of styles['shape'] = 'ellipse'

    # Color (note that the old 'Flat out red' is never used
    if node.group.acronym == 'none':
        styles['color'] = '"#FF800D"' # orangeish
    elif node.group == group:
        styles['color'] = '"#0AFE47"' # greenish
    else:
        styles['color'] = '"#9999FF"' # blueish

    # Label
    label = node.name
    if label.startswith('draft-'):
        if label.startswith('draft-ietf-'):
            label=label[11:]
        else:
            label=label[6:]
        try:
            t=label.index('-')
            label="%s\\n%s" % (label[:t],label[t+1:])
        except:
            pass
    if node.group.acronym != 'none' and node.group != group:
        label = "(%s) %s"%(node.group.acronym,label)
    if node.get_state('draft').slug == 'rfc':
        label = "%s\\n(%s)"%(label,node.canonical_name())
    styles['label'] = '"%s"'%label

    return styles

def make_dot(group):

    references = Q(source__group=group,source__type='draft',relationship__slug__startswith='ref')
    both_rfcs  = Q(source__states__slug='rfc',target__document__states__slug='rfc')
    inactive   = Q(source__states__slug__in=['expired','repl'])
    attractor  = Q(target__name__in=['rfc5000','rfc5741'])
    removed    = Q(source__states__slug__in=['auth-rm','ietf-rm'])
    relations = RelatedDocument.objects.filter(references).exclude(both_rfcs).exclude(inactive).exclude(attractor).exclude(removed)

    edges = set()
    for x in relations:
        target_state = x.target.document.get_state_slug('draft')
        if target_state!='rfc' or x.is_downref():
            edges.add(Edge(x))

    replacements = RelatedDocument.objects.filter(relationship__slug='replaces',target__document__in=[x.relateddocument.target.document for x in edges])

    for x in replacements:
        edges.add(Edge(x))

    nodes = set([x.relateddocument.source for x in edges]).union([x.relateddocument.target.document for x in edges])

    for node in nodes:
        node.nodename=nodename(node.name)
        node.styles = get_node_styles(node,group)

    return render_to_string('group/dot.txt',
                             dict( nodes=nodes, edges=edges )
                            )

def dependencies_dot(request, acronym, group_type=None):
    group = get_group_or_404(acronym, group_type)
    if not group.features.has_documents:
        raise Http404

    return HttpResponse(make_dot(group),
                        content_type='text/plain; charset=UTF-8'
                        )

@cache_page ( 60 * 60 )
def dependencies_pdf(request, acronym, group_type=None):
    group = get_group_or_404(acronym, group_type)
    if not group.features.has_documents:
        raise Http404

    dothandle,dotname = mkstemp()  
    os.close(dothandle)
    dotfile = open(dotname,"w")
    dotfile.write(make_dot(group))
    dotfile.close()

    unflathandle,unflatname = mkstemp()
    os.close(unflathandle)

    pshandle,psname = mkstemp()
    os.close(pshandle)

    pdfhandle,pdfname = mkstemp()
    os.close(pdfhandle)

    pipe("%s -f -l 10 -o %s %s" % (settings.UNFLATTEN_BINARY,unflatname,dotname))
    pipe("%s -Tps -Gsize=10.5,8.0 -Gmargin=0.25 -Gratio=auto -Grotate=90 -o %s %s" % (settings.DOT_BINARY,psname,unflatname))
    pipe("%s %s %s" % (settings.PS2PDF_BINARY,psname,pdfname))
    
    pdfhandle = open(pdfname,"r")
    pdf = pdfhandle.read()
    pdfhandle.close()

    os.unlink(pdfname)
    os.unlink(psname)
    os.unlink(unflatname)
    os.unlink(dotname)

    return HttpResponse(pdf, content_type='application/pdf')

def email_aliases(request, acronym=None, group_type=None):
    group = get_group_or_404(acronym,group_type) if acronym else None

    if not acronym:
        # require login for the overview page, but not for the group-specific
        # pages 
        if not request.user.is_authenticated():
                return redirect('%s?next=%s' % (settings.LOGIN_URL, request.path))

    aliases = get_email_aliases(acronym, group_type)

    return render(request,'group/email_aliases.html',{'aliases':aliases,'ietf_domain':settings.IETF_DOMAIN,'group':group})

