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
from django.conf import settings
from ietf.doc.models import GroupBallotPositionDocEvent, WriteupDocEvent
from ietf.group.models import Group, GroupHistory
from ietf.person.models import Person
from ietf.wgcharter import markup_txt

from ietf.wgcharter.utils import *
from ietf.utils.history import find_history_active_at
from ietf.idtracker.templatetags.ietf_filters import format_textarea, fill
 
# FIXME: delete
def _get_html(key, filename):
    f = None
    try:
        f = open(filename, 'rb')
        raw_content = f.read()
    except IOError:
        return "Error; cannot read ("+key+")"
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
            return redirect('wg_view', name=wglist[0].group.acronym)
        else:
            raise Http404

    if not wg.charter:
        set_or_create_charter(wg)

    if rev != None:
        ch = get_charter_for_revision(wg.charter, rev)
        gh = get_group_for_revision(wg, rev)
    else:
        ch = get_charter_for_revision(wg.charter, wg.charter.rev)
        gh = get_group_for_revision(wg, wg.charter.rev)


    info = {}

    info['prev_acronyms'] = list(set([x.acronym for x in wg.history_set.exclude(acronym=wg.acronym)]))
    prev_list_email = list(set([x.list_email for x in wg.history_set.exclude(list_email=wg.list_email) if x.list_email != u'']))
    if prev_list_email != [u'']:
        info['prev_list_email'] = prev_list_email
    prev_list_subscribe = list(set([x.list_subscribe for x in wg.history_set.exclude(list_subscribe=wg.list_subscribe) if x.list_subscribe != u'']))
    if prev_list_subscribe != [u'']:
        info['prev_list_subscribe'] = prev_list_subscribe    
    prev_list_archive = list(set([x.list_archive for x in wg.history_set.exclude(list_archive=wg.list_archive) if x.list_archive != u'']))
    if prev_list_archive != [u'']:
        info['prev_list_archive'] = prev_list_archive
    info['chairs'] = [x.person.plain_name() for x in wg.role_set.filter(name__slug="chair")]
    if hasattr(gh, 'rolehistory_set'):
        info['history_chairs'] = [x.person.plain_name() for x in gh.rolehistory_set.filter(name__slug="chair")]
    else:
        info['history_chairs'] = [x.person.plain_name() for x in gh.role_set.filter(name__slug="chair")]
    info['secr'] = [x.person.plain_name() for x in wg.role_set.filter(name__slug="secr")]
    info['techadv'] = [x.person.plain_name() for x in wg.role_set.filter(name__slug="techadv")]

    if ch:
        file_path = wg.charter.get_file_path() # Get from wg.charter
        content = _get_html(
            "charter-ietf-"+str(gh.acronym)+"-"+str(ch.rev)+".txt", 
            os.path.join(file_path, "charter-ietf-"+gh.acronym+"-"+ch.rev+".txt"))
        active_ads = Person.objects.filter(email__role__name="ad", email__role__group__state="active").distinct()
        started_process = datetime.min
        e = wg.charter.latest_event(type="started_iesg_process")
        if e:
            started_process = e.time
        seen = []
        latest_positions = []
        for p in GroupBallotPositionDocEvent.objects.filter(doc=wg.charter, type="changed_ballot_position", time__gte=started_process).order_by("-time", '-id').select_related('ad'):
            if p.ad not in seen:
                latest_positions.append(p)
                seen.append(p.ad)
        no_record = []
        old_ads = []
        for p in latest_positions:
            if p.ad not in active_ads:
                old_ads.append(p.ad)
        for ad in active_ads:
            has_no_record = True
            for p in latest_positions:
                if p.ad == ad:
                    has_no_record = False
            if has_no_record:
                no_record.append(ad)

        info['old_ads'] = old_ads
        info['positions'] = latest_positions
        info['pos_yes'] = filter(lambda x: x.pos_id == "yes", latest_positions)
        info['pos_no'] = filter(lambda x: x.pos_id == "no", latest_positions)
        info['pos_block'] = filter(lambda x: x.pos_id == "block", latest_positions)
        info['pos_abstain'] = filter(lambda x: x.pos_id == "abstain", latest_positions)
        info['pos_no_record'] = no_record + [x.ad for x in latest_positions if x.pos_id == "norecord"]
        
        # Get announcement texts
        review_ann = wg.charter.latest_event(WriteupDocEvent, type="changed_review_announcement")
        info['review_text'] = review_ann.text if review_ann else ""
        action_ann = wg.charter.latest_event(WriteupDocEvent, type="changed_action_announcement")
        info['action_text'] = action_ann.text if action_ann else ""
        ballot_ann = wg.charter.latest_event(WriteupDocEvent, type="changed_ballot_writeup_text")
        info['ballot_text'] = ballot_ann.text if ballot_ann else ""
    else:
        content = ""

    versions = _get_versions(wg.charter) # Important: wg.charter not ch
    history = _get_history(wg, versions)

    if history:
        info['last_update'] = history[0]['date']

    template = "wgcharter/wg_tab_%s" % tab
    return render_to_response(template + ".html",
                              {'content':content,
                               'charter':ch,
                               'info':info,
                               'wg':wg,
                               'tab':tab,
                               'rev': rev if rev else ch.rev,
                               'gh': gh,
                               'snapshot': rev,
                               'charter_text_url': settings.CHARTER_TXT_URL,
                               'history': history, 'versions': versions,
			       },
                              context_instance=RequestContext(request))

def _get_history(wg, versions=None):
    results = []
    for e in wg.charter.docevent_set.all().order_by('-time'):
        info = {}
        charter_history = find_history_active_at(wg.charter, e.time)
        info['version'] = charter_history.rev if charter_history else wg.charter.rev
        info['text'] = e.desc
        info['by'] = e.by.plain_name()
        info['textSnippet'] = truncatewords_html(format_textarea(fill(info['text'], 80)), 25)
        info['snipped'] = info['textSnippet'][-3:] == "..."
        if e.type == "new_revision":
            if charter_history:
                charter = get_charter_for_revision(wg.charter, charter_history.rev)
                group = get_group_for_revision(wg, charter_history.rev)
            else:
                charter = get_charter_for_revision(wg.charter, wg.charter.rev)
                group = get_group_for_revision(wg, wg.charter.rev)

            if versions:
                vl = [x['rev'] for x in versions]
                if vl:
                    prev_charter = get_charter_for_revision(wg.charter, vl[vl.index(charter.rev) - 1])
            else:
                prev_charter = get_charter_for_revision(wg.charter, prev_revision(charter.rev))
            prev_group = get_group_for_revision(wg, prev_revision(charter.rev))
            results.append({'comment':e, 'info':info, 'date':e.time, 'group': group,
                            'charter': charter, 'prev_charter': prev_charter,
                            'prev_group': prev_group,
                            'txt_url': settings.CHARTER_TXT_URL,
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
    prev = ""
    for r in charter.history_set.order_by('time'):
        if r.rev != prev:
            d = get_charter_for_revision(charter, r.rev)
            g = get_group_for_revision(charter.chartered_group, r.rev)
            ov.append({"name": "charter-ietf-%s" % g.acronym, "rev":d.rev, "date":d.time})
            prev = r.rev
    if charter.rev != "" and (not ov or ov[-1]['rev'] != charter.rev):
        d = get_charter_for_revision(charter, charter.rev)
        g = get_group_for_revision(charter.chartered_group, charter.rev)
        ov.append({"name": "charter-ietf-%s" % g.acronym, "rev": d.rev, "date":d.time})
    return ov

def wg_ballot(request, name):
    try:
        wg = Group.objects.get(acronym=name)
    except ObjectDoesNotExist:
        wglist = GroupHistory.objects.filter(acronym=name)
        if wglist:
            return redirect('wg_view', name=wglist[0].group.acronym)
        else:
            raise Http404

    doc = set_or_create_charter(wg)

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
    return render_to_response('wgcharter/wg_ballot.html', {'info':info, 'wg':wg, 'doc': doc}, context_instance=RequestContext(request))


def json_emails(l):
    result = []
    for p in l:
        result.append({"id": p.address + "", "name": p.person.plain_name() + " &lt;" + p.address + "&gt;"})
    return simplejson.dumps(result)

def search_person(request):
    if request.method == 'GET':
        emails = Email.objects.filter(person__name__istartswith=request.GET.get('q','')).order_by('person__name')
        return HttpResponse(json_emails(emails), mimetype='application/json')
