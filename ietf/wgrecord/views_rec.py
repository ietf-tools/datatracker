# Copyright The IETF Trust 2011, All Rights Reserved

import re, os
from datetime import datetime, time

from django.http import HttpResponse, Http404
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.template import RequestContext
from django.template.defaultfilters import truncatewords_html
from django.utils import simplejson as json
from django.utils.decorators import decorator_from_middleware
from django.middleware.gzip import GZipMiddleware
from django.core.exceptions import ObjectDoesNotExist
from redesign.doc.models import Document, DocHistory, GroupBallotPositionDocEvent, WriteupDocEvent
from redesign.group.models import Group, GroupHistory
from redesign.person.models import Person
from wgrecord import markup_txt
from django.conf import settings

from wgrecord.utils import *
from ietf.utils.history import find_history_active_at
from ietf.idtracker.templatetags.ietf_filters import format_textarea, fill
 
def _get_html(key, filename):
    f = None
    try:
        f = open(filename, 'rb')
        raw_content = f.read()
    except IOError:
        return ("Error; cannot read ("+key+")", "")
    finally:
        if f:
            f.close()
    content = markup_txt.markup(raw_content)
    return content

@decorator_from_middleware(GZipMiddleware)
def wg_main(request, name, rev, tab):
    if tab is None:
	tab = "charter"
    try:
        wg = Group.objects.get(acronym=name)
    except ObjectDoesNotExist:
        wglist = GroupHistory.objects.filter(acronym=name)
        if wglist:
            return redirect('wg_view_record', name=wglist[0].group.acronym)
        else:
            raise Http404

    if not wg.charter:
        create_empty_charter(wg)

    if rev != None:
        charter = get_charter_for_revision(wg.charter, rev)
        gh = get_group_for_revision(wg, rev)
    else:
        charter = get_charter_for_revision(wg.charter, wg.charter.rev)
        gh = get_group_for_revision(wg, wg.charter.rev)

    info = {}

    info['prev_acronyms'] = list(set([x.acronym for x in wg.history_set.exclude(acronym=wg.acronym)]))
    prev_list_email = list(set([x.list_email for x in wg.history_set.exclude(list_email=wg.list_email)]))
    if prev_list_email != [u'']:
        info['prev_list_email'] = prev_list_email
    prev_list_subscribe = list(set([x.list_email for x in wg.history_set.exclude(list_subscribe=wg.list_subscribe)]))
    if prev_list_subscribe != [u'']:
        info['prev_list_subscribe'] = prev_list_subscribe    
    prev_list_archive = list(set([x.list_archive for x in wg.history_set.exclude(list_archive=wg.list_archive)]))
    if prev_list_archive != [u'']:
        info['prev_list_archive'] = prev_list_archive
    info['chairs'] = [x.email.person.name for x in wg.role_set.filter(name__slug="chair")]
    if hasattr(gh, 'rolehistory_set'):
        info['history_chairs'] = [x.email.person.name for x in gh.rolehistory_set.filter(name__slug="chair")]
    else:
        info['history_chairs'] = [x.email.person.name for x in gh.role_set.filter(name__slug="chair")]
    info['secr'] = [x.email.person.name for x in wg.role_set.filter(name__slug="secr")]
    info['techadv'] = [x.email.person.name for x in wg.role_set.filter(name__slug="techadv")]

    if charter:
        content = _get_html(
            str(charter.name)+"-"+str(charter.rev)+",html", 
            os.path.join(charter.get_file_path(), charter.name+"-"+charter.rev+".txt"))
        active_ads = list(Person.objects.filter(email__role__name="ad",
                                                email__role__group__type="area",
                                                email__role__group__state="active").distinct())
        started_process = wg.charter.latest_event(type="started_iesg_process")
        latest_positions = []
        no_record = []
        for p in active_ads:
            p_pos = list(GroupBallotPositionDocEvent.objects.filter(doc=wg.charter, ad=p).order_by("-time"))
            if p_pos != []:
                latest_positions.append(p_pos[0])
            else:
                no_record.append(p)
        info = {}
        info['positions'] = latest_positions
        info['pos_yes'] = filter(lambda x: x.pos_id == "yes", latest_positions)
        info['pos_no'] = filter(lambda x: x.pos_id == "no", latest_positions)
        info['pos_block'] = filter(lambda x: x.pos_id == "block", latest_positions)
        info['pos_abstain'] = filter(lambda x: x.pos_id == "abstain", latest_positions)
        info['pos_no_record'] = no_record
        
        # Get annoucement texts
        review_ann = wg.charter.latest_event(WriteupDocEvent, type="changed_review_announcement")
        info['review_text'] = review_ann.text if review_ann else ""
        action_ann = wg.charter.latest_event(WriteupDocEvent, type="changed_action_announcement")
        info['action_text'] = action_ann.text if action_ann else ""
    else:
        content = ""

    versions = _get_versions(wg.charter) # Important: wg.charter not charter
    history = _get_history(wg)

    if history:
        info['last_update'] = history[0]['date']

    charter_text_url = charter.get_txt_url()

    template = "wgrecord/record_tab_%s" % tab
    return render_to_response(template + ".html",
                              {'content':content,
                               'charter':charter, 'info':info, 'wg':wg, 'tab':tab,
                               'rev': rev if rev else charter.rev, 'gh': gh,
                               'snapshot': rev, 'charter_text_url': charter_text_url,
                               'history': history, 'versions': versions,
			       },
                              context_instance=RequestContext(request));

def _get_history(wg):
    results = []
    for e in wg.groupevent_set.all().select_related('by').order_by('-time', 'id'):
        info = {}
                    
        charter_history = find_history_active_at(wg.charter, e.time)
        info['version'] = charter_history.rev if charter_history else wg.charter.rev
        info['text'] = e.desc
        info['by'] = e.by.name
        info['textSnippet'] = truncatewords_html(format_textarea(fill(info['text'], 80)), 25)
        info['snipped'] = info['textSnippet'][-3:] == "..."
        results.append({'comment':e, 'info':info, 'date':e.time, 'group': wg, 'is_com':True})

    for e in wg.charter.docevent_set.all().order_by('-time'):
        info = {}
        charter_history = find_history_active_at(wg.charter, e.time)
        info['version'] = charter_history.rev if charter_history else wg.charter.rev
        info['text'] = e.desc
        info['by'] = e.by.name
        info['textSnippet'] = truncatewords_html(format_textarea(fill(info['text'], 80)), 25)
        info['snipped'] = info['textSnippet'][-3:] == "..."
        if e.type == "new_revision":
            if charter_history:
                charter = get_charter_for_revision(wg.charter, charter_history.rev)
            else:
                charter = get_charter_for_revision(wg.charter, wg.charter.rev)

            prev_charter = get_charter_for_revision(wg.charter, prev_revision(charter.rev))
            results.append({'comment':e, 'info':info, 'date':e.time, 'group': wg,
                            'charter': charter, 'prev_charter': prev_charter,
                            'txt_url': wg.charter.get_txt_url(), 
                            'is_rev':True})
        else:
            results.append({'comment':e, 'info':info, 'date':e.time, 'group': wg, 'is_com':True})

    # convert plain dates to datetimes (required for sorting)
    for x in results:
        if not isinstance(x['date'], datetime):
            if x['date']:
                x['date'] = datetime.combine(x['date'], time(0,0,0))
            else:
                x['date'] = datetime(1970,1,1)

    results.sort(key=lambda x: x['date'])
    results.reverse()
    return results

def _get_versions(charter, include_replaced=True):
    ov = []
    for r in sorted(list(set(charter.history_set.values_list('rev', flat=True)))):
        if r != "":
            d = get_charter_for_revision(charter, r)
            if d.rev != charter.rev:
                ov.append({"name":d.name, "rev":d.rev, "date":d.time})
    if charter.rev != "":
        ov.append({"name": charter.name, "rev": charter.rev, "date":charter.time})
    return ov

def wg_ballot(request, name):
    try:
        wg = Group.objects.get(acronym=name)
    except ObjectDoesNotExist:
        wglist = GroupHistory.objects.filter(acronym=name)
        if wglist:
            return redirect('wg_view_record', name=wglist[0].group.acronym)
        else:
            raise Http404

    doc = wg.charter

    if not doc:
        raise Http404

    active_ads = list(Person.objects.filter(email__role__name="ad",
                                            email__role__group__type="area",
                                            email__role__group__state="active").distinct())
    started_process = doc.latest_event(type="started_iesg_process")
    latest_positions = []
    no_record = []
    for p in active_ads:
        p_pos = list(GroupBallotPositionDocEvent.objects.filter(doc=wg.charter, ad=p).order_by("-time"))
        if p_pos != []:
            latest_positions.append(p_pos[0])
        else:
            no_record.append(p)
    info = {}
    info['positions'] = latest_positions
    info['pos_yes'] = filter(lambda x: x.pos_id == "yes", latest_positions)
    info['pos_no'] = filter(lambda x: x.pos_id == "no", latest_positions)
    info['pos_block'] = filter(lambda x: x.pos_id == "block", latest_positions)
    info['pos_abstain'] = filter(lambda x: x.pos_id == "abstain", latest_positions)
    info['pos_no_record'] = no_record
    return render_to_response('wgrecord/record_ballot.html', {'info':info, 'wg':wg, 'doc': doc}, context_instance=RequestContext(request))

