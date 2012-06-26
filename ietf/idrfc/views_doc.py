# Copyright (C) 2009-2010 Nokia Corporation and/or its subsidiary(-ies).
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

import re, os, datetime

from django.http import HttpResponse, Http404
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.template import RequestContext
from django.template.loader import render_to_string
from django.template.defaultfilters import truncatewords_html
from django.utils import simplejson as json
from django.utils.decorators import decorator_from_middleware
from django.middleware.gzip import GZipMiddleware
from django.core.urlresolvers import reverse as urlreverse, NoReverseMatch
from django.conf import settings

from ietf.idtracker.models import InternetDraft, IDInternal, BallotInfo, DocumentComment
from ietf.idtracker.templatetags.ietf_filters import format_textarea, fill
from ietf.idrfc import markup_txt
from ietf.idrfc.models import RfcIndex, DraftVersions
from ietf.idrfc.idrfc_wrapper import BallotWrapper, IdWrapper, RfcWrapper
from ietf.ietfworkflows.utils import get_full_info_for_draft
from ietf.doc.models import *
from ietf.doc.utils import *
from ietf.utils.history import find_history_active_at
from ietf.ietfauth.decorators import has_role


def render_document_top(request, doc, tab, name):
    tabs = []
    tabs.append(("Document", "document", urlreverse("ietf.idrfc.views_doc.document_main", kwargs=dict(name=name)), True))

    ballot = doc.latest_event(BallotDocEvent, type="created_ballot")
    if doc.type_id == "draft":
        # if doc.in_ietf_process and doc.ietf_process.has_iesg_ballot:
        tabs.append(("IESG Evaluation Record", "ballot", urlreverse("ietf.idrfc.views_doc.document_ballot", kwargs=dict(name=name)), ballot))
    elif doc.type_id == "charter":
        tabs.append(("IESG Review", "ballot", urlreverse("ietf.idrfc.views_doc.document_ballot", kwargs=dict(name=name)), ballot))

    # FIXME: if doc.in_ietf_process and doc.ietf_process.has_iesg_ballot:
    tabs.append(("IESG Writeups", "writeup", urlreverse("ietf.idrfc.views_doc.document_writeup", kwargs=dict(name=name)), True))
    tabs.append(("History", "history", urlreverse("ietf.idrfc.views_doc.document_history", kwargs=dict(name=name)), True))

    name = doc.canonical_name()
    if name.startswith("rfc"):
        name = "RFC %s" % name[3:]
    else:
        name += "-" + doc.rev

    return render_to_string("idrfc/document_top.html",
                            dict(doc=doc,
                                 tabs=tabs,
                                 selected=tab,
                                 name=name))


def document_main(request, name, rev=None):
    if name.lower().startswith("draft") or name.lower().startswith("rfc"):
        if rev != None: # no support for old revisions at the moment
            raise Http404()
        return document_main_idrfc(request, name, tab="document")

    doc = get_object_or_404(Document, docalias__name=name)
    group = doc.group

    revisions = []
    for h in doc.history_set.order_by("time", "id"):
        if h.rev and not h.rev in revisions:
            revisions.append(h.rev)
    if not doc.rev in revisions:
        revisions.append(doc.rev)

    snapshot = False

    if rev != None:
        if rev == doc.rev:
            return redirect('doc_view', name=name)

        # find the entry in the history
        for h in doc.history_set.order_by("-time"):
            if rev == h.rev:
                snapshot = True
                doc = h
                break

        if not snapshot:
            return redirect('doc_view', name=name)

        # find old group, too
        gh = find_history_active_at(doc.group, doc.time)
        if gh:
            group = gh

    top = render_document_top(request, doc, "document", name)


    telechat = doc.latest_event(TelechatDocEvent, type="scheduled_for_telechat")
    if telechat and telechat.telechat_date < datetime.date.today():
        telechat = None

    if doc.type_id == "charter":
        filename = "%s-%s.txt" % (doc.canonical_name(), doc.rev)

        content = _get_html(filename, os.path.join(settings.CHARTER_PATH, filename), split=False)

        ballot_summary = None
        if doc.get_state_slug() in ("intrev", "iesgrev"):
            ballot_summary = needed_ballot_positions(doc, active_ballot_positions(doc).values())

        chartering = get_chartering_type(doc)

        # inject milestones from group
        milestones = None
        if chartering and not snapshot:
            milestones = doc.group.groupmilestone_set.filter(state="charter")

        return render_to_response("idrfc/document_charter.html",
                                  dict(doc=doc,
                                       top=top,
                                       chartering=chartering,
                                       content=content,
                                       txt_url=settings.CHARTER_TXT_URL + filename,
                                       revisions=revisions,
                                       snapshot=snapshot,
                                       telechat=telechat,
                                       ballot_summary=ballot_summary,
                                       group=group,
                                       milestones=milestones,
                                       ),
                                  context_instance=RequestContext(request))

    raise Http404()


def document_history(request, name):
    # todo: remove need for specific handling of drafts by porting the
    # two event text hacks
    if name.lower().startswith("draft") or name.lower().startswith("rfc"):
        return document_main_idrfc(request, name, "history")

    doc = get_object_or_404(Document, docalias__name=name)
    top = render_document_top(request, doc, "history", name)

    diff_documents = [ doc ]
    diff_documents.extend(Document.objects.filter(docalias__relateddocument__source=doc, docalias__relateddocument__relationship="replaces"))

    # pick up revisions from events
    diff_revisions = []
    seen = set()

    diffable = name.startswith("draft") or name.startswith("charter")

    if diffable:
        for e in NewRevisionDocEvent.objects.filter(type="new_revision", doc__in=diff_documents).select_related('doc').order_by("-time", "-id"):
            if not (e.doc.name, e.rev) in seen:
                seen.add((e.doc.name, e.rev))

                url = ""
                if name.startswith("charter"):
                    h = find_history_active_at(e.doc, e.time)
                    url = settings.CHARTER_TXT_URL + ("%s-%s.txt" % ((h or doc).canonical_name(), e.rev))
                elif name.startswith("draft"):
                    # rfcdiff tool has special support for IDs
                    url = e.doc.name + "-" + e.rev

                diff_revisions.append((e.doc.name, e.rev, e.time, url))

    # grab event history
    events = doc.docevent_set.all().order_by("-time", "-id").select_related("by")

    augment_events_with_revision(doc, events)

    return render_to_response("idrfc/document_history.html",
                              dict(doc=doc,
                                   top=top,
                                   diff_revisions=diff_revisions,
                                   events=events,
                                   ),
                              context_instance=RequestContext(request))

def document_writeup(request, name):
    if name.lower().startswith("draft") or name.lower().startswith("rfc"):
        # todo: migrate idrfc to pattern below
        return document_main_idrfc(request, name, "writeup")

    doc = get_object_or_404(Document, docalias__name=name)
    top = render_document_top(request, doc, "writeup", name)

    writeups = []
    if doc.type_id == "charter":
        e = doc.latest_event(WriteupDocEvent, type="changed_review_announcement")
        writeups.append(("WG Review Announcement",
                         e.text if e else "",
                         urlreverse("ietf.wgcharter.views.announcement_text", kwargs=dict(name=doc.name, ann="review"))))

        e = doc.latest_event(WriteupDocEvent, type="changed_action_announcement")
        writeups.append(("WG Action Announcement",
                         e.text if e else "",
                         urlreverse("ietf.wgcharter.views.announcement_text", kwargs=dict(name=doc.name, ann="action"))))

        if doc.latest_event(BallotDocEvent, type="created_ballot"):
            e = doc.latest_event(WriteupDocEvent, type="changed_ballot_writeup_text")
            writeups.append(("Ballot Announcement",
                             e.text if e else "",
                             urlreverse("ietf.wgcharter.views.ballot_writeupnotes", kwargs=dict(name=doc.name))))

    if not writeups:
        raise Http404()

    return render_to_response("idrfc/document_writeup.html",
                              dict(doc=doc,
                                   top=top,
                                   writeups=writeups,
                                   can_edit=has_role(request.user, ("Area Director", "Secretariat")),
                                   ),
                              context_instance=RequestContext(request))

def document_ballot_content(request, doc, ballot_id, editable=True):
    """Render HTML string with content of ballot page."""
    all_ballots = list(BallotDocEvent.objects.filter(doc=doc, type="created_ballot").order_by("time"))
    augment_events_with_revision(doc, all_ballots)

    ballot = None
    if ballot_id != None:
        ballot_id = int(ballot_id)
        for b in all_ballots:
            if b.id == ballot_id:
                ballot = b
                break
    elif all_ballots:
        ballot = all_ballots[-1]

    if not ballot:
        raise Http404

    deferred = None
    if doc.type_id == "draft" and doc.get_state_slug("draft-iesg") == "defer":
        # FIXME: fragile
        deferred = doc.latest_event(type="changed_document", desc__startswith="State changed to <b>IESG Evaluation - Defer</b>")

    # collect positions
    active_ads = list(Person.objects.filter(role__name="ad", role__group__state="active").distinct())

    positions = []
    seen = {}
    for e in BallotPositionDocEvent.objects.filter(doc=doc, type="changed_ballot_position", ballot=ballot).select_related('ad', 'pos').order_by("-time", '-id'):
        if e.ad not in seen:
            e.old_ad = e.ad not in active_ads
            e.old_positions = []
            positions.append(e)
            seen[e.ad] = e
        else:
            latest = seen[e.ad]
            if latest.old_positions:
                prev = latest.old_positions[-1]
            else:
                prev = latest.pos.name

            if e.pos.name != prev:
                latest.old_positions.append(e.pos.name)

    # add any missing ADs through fake No Record events
    norecord = BallotPositionName.objects.get(slug="norecord")
    for ad in active_ads:
        if ad not in seen:
            e = BallotPositionDocEvent(type="changed_ballot_position", doc=doc, ad=ad)
            e.pos = norecord
            e.old_ad = False
            e.old_positions = []
            positions.append(e)

    # put into position groups
    position_groups = []
    for n in BallotPositionName.objects.filter(slug__in=[p.pos_id for p in positions]).order_by('order'):
        g = (n, [p for p in positions if p.pos_id == n.slug])
        g[1].sort(key=lambda p: (p.old_ad, p.ad.plain_name()))
        if n.blocking:
            position_groups.insert(0, g)
        else:
            position_groups.append(g)

    summary = needed_ballot_positions(doc, [p for p in positions if not p.old_ad])

    text_positions = [p for p in positions if p.discuss or p.comment]
    text_positions.sort(key=lambda p: (p.old_ad, p.ad.plain_name()))

    ballot_open = not BallotDocEvent.objects.filter(doc=doc,
                                                    type__in=("closed_ballot", "created_ballot"),
                                                    time__gt=ballot.time,
                                                    ballot_type=ballot.ballot_type)
    if not ballot_open:
        editable = False

    return render_to_string("idrfc/document_ballot_content.html",
                              dict(doc=doc,
                                   ballot=ballot,
                                   position_groups=position_groups,
                                   text_positions=text_positions,
                                   editable=editable,
                                   ballot_open=ballot_open,
                                   deferred=deferred,
                                   summary=summary,
                                   all_ballots=all_ballots,
                                   ),
                              context_instance=RequestContext(request))

def document_ballot(request, name, ballot_id=None):
    doc = get_object_or_404(Document, docalias__name=name)
    top = render_document_top(request, doc, "ballot", name)

    c = document_ballot_content(request, doc, ballot_id, editable=True)

    return render_to_response("idrfc/document_ballot.html",
                              dict(doc=doc,
                                   top=top,
                                   ballot_content=c,
                                   ),
                              context_instance=RequestContext(request))

def document_debug(request, name):
    r = re.compile("^rfc([1-9][0-9]*)$")
    m = r.match(name)
    if m:
        rfc_number = int(m.group(1))
        rfci = get_object_or_404(RfcIndex, rfc_number=rfc_number)
        doc = RfcWrapper(rfci)
    else:
        id = get_object_or_404(InternetDraft, filename=name)
        doc = IdWrapper(draft=id)
    return HttpResponse(doc.to_json(), mimetype='text/plain')

def _get_html(key, filename, split=True):
    f = None
    try:
        f = open(filename, 'rb')
        raw_content = f.read()
    except IOError:
        error = "Error; cannot read '%s'" % key
        if split:
            return (error, "")
        else:
            return error
    finally:
        if f:
            f.close()
    return markup_txt.markup(raw_content, split)

def include_text(request):
    include_text = request.GET.get( 'include_text' )
    if "full_draft" in request.COOKIES:
        if request.COOKIES["full_draft"] == "on":
            include_text = 1
    return include_text

def document_main_rfc(request, rfc_number, tab):
    rfci = get_object_or_404(RfcIndex, rfc_number=rfc_number, states__type="draft", states__slug="rfc")
    rfci.viewing_as_rfc = True
    doc = RfcWrapper(rfci)

    info = {}
    info['is_rfc'] = True
    info['has_pdf'] = (".pdf" in doc.file_types())
    info['has_txt'] = (".txt" in doc.file_types())
    info['has_ps'] = (".ps" in doc.file_types())
    if info['has_txt']:
        (content1, content2) = _get_html(
            "rfc"+str(rfc_number)+",html", 
            os.path.join(settings.RFC_PATH, "rfc"+str(rfc_number)+".txt"))
    else:
        content1 = ""
        content2 = ""

    history = _get_history(doc, None)
            
    template = "idrfc/doc_tab_%s" % tab
    if tab == "document":
	template += "_rfc"
    return render_to_response(template + ".html",
                              {'content1':content1, 'content2':content2,
                               'doc':doc, 'info':info, 'tab':tab,
			       'include_text':include_text(request),
                               'history':history},
                              context_instance=RequestContext(request));

@decorator_from_middleware(GZipMiddleware)
def document_main_idrfc(request, name, tab):
    r = re.compile("^rfc([1-9][0-9]*)$")
    m = r.match(name)
    if m:
        return document_main_rfc(request, int(m.group(1)), tab)
    id = get_object_or_404(InternetDraft, filename=name)
    doc = IdWrapper(id) 

    info = {}
    info['has_pdf'] = (".pdf" in doc.file_types())
    info['is_rfc'] = False
    
    (content1, content2) = _get_html(
        str(name)+","+str(id.revision)+",html",
        os.path.join(settings.INTERNET_DRAFT_PATH, name+"-"+id.revision+".txt"))

    versions = _get_versions(id)
    history = _get_history(doc, versions)
            
    template = "idrfc/doc_tab_%s" % tab
    if tab == "document":
	template += "_id"
    return render_to_response(template + ".html",
                              {'content1':content1, 'content2':content2,
                               'doc':doc, 'info':info, 'tab':tab,
			       'include_text':include_text(request),
                               'stream_info': get_full_info_for_draft(id),
                               'versions':versions, 'history':history},
                              context_instance=RequestContext(request));

# doc is either IdWrapper or RfcWrapper
def _get_history(doc, versions):
    results = []
    if settings.USE_DB_REDESIGN_PROXY_CLASSES:
        versions = [] # clear versions
        event_holder = doc._draft if hasattr(doc, "_draft") else doc._rfcindex
        for e in event_holder.docevent_set.all().select_related('by').order_by('-time', 'id'):
            info = {}
            if e.type == "new_revision":
                filename = u"%s-%s" % (e.doc.name, e.newrevisiondocevent.rev)
                e.desc = 'New version available: <a href="http://tools.ietf.org/id/%s.txt">%s</a>' % (filename, filename)
                if int(e.newrevisiondocevent.rev) != 0:
                    e.desc += ' (<a href="http://tools.ietf.org/rfcdiff?url2=%s">diff from -%02d</a>)' % (filename, int(e.newrevisiondocevent.rev) - 1)
                info["dontmolest"] = True

            multiset_ballot_text = "This was part of a ballot set with: "
            if e.desc.startswith(multiset_ballot_text):
                names = [ n.strip() for n in e.desc[len(multiset_ballot_text):].split(",") ]
                e.desc = multiset_ballot_text + ", ".join(u'<a href="%s">%s</a>' % (urlreverse("doc_view", kwargs={'name': n }), n) for n in names)
                info["dontmolest"] = True
                    
            info['text'] = e.desc
            info['by'] = e.by.plain_name()
            info['textSnippet'] = truncatewords_html(format_textarea(fill(info['text'], 80)), 25)
            info['snipped'] = info['textSnippet'][-3:] == "..." and e.type != "new_revision"
            results.append({'comment':e, 'info':info, 'date':e.time, 'is_com':True})

        prev_rev = "00"
        # actually, we're already sorted and this ruins the sort from
        # the ids which is sometimes needed, so the function should be
        # rewritten to not rely on a resort
        results.sort(key=lambda x: x['date'])
        for o in results:
            e = o["comment"]
            if e.type == "new_revision":
                e.version = e.newrevisiondocevent.rev
            else:
                e.version = prev_rev
            prev_rev = e.version
    else:
        if doc.is_id_wrapper:
            comments = DocumentComment.objects.filter(document=doc.tracker_id).exclude(rfc_flag=1)
        else:
            comments = DocumentComment.objects.filter(document=doc.rfc_number,rfc_flag=1)
            if len(comments) > 0:
                # also include rfc_flag=NULL, but only if at least one
                # comment with rfc_flag=1 exists (usually NULL means same as 0)
                comments = DocumentComment.objects.filter(document=doc.rfc_number).exclude(rfc_flag=0)
        for comment in comments.order_by('-date','-time','-id').filter(public_flag=1).select_related('created_by'):
            info = {}
            info['text'] = comment.comment_text
            info['by'] = comment.get_fullname()
            info['textSnippet'] = truncatewords_html(format_textarea(fill(info['text'], 80)), 25)
            info['snipped'] = info['textSnippet'][-3:] == "..."
            results.append({'comment':comment, 'info':info, 'date':comment.datetime(), 'is_com':True})
    
    if doc.is_id_wrapper and versions:
        for v in versions:
            if v['draft_name'] == doc.draft_name:
                v = dict(v) # copy it, since we're modifying datetimes later
                v['is_rev'] = True
                results.insert(0, v)    
    if not settings.USE_DB_REDESIGN_PROXY_CLASSES and doc.is_id_wrapper and doc.draft_status == "Expired" and doc._draft.expiration_date:
        results.append({'is_text':True, 'date':doc._draft.expiration_date, 'text':'Draft expired'})
    if not settings.USE_DB_REDESIGN_PROXY_CLASSES and doc.is_rfc_wrapper:
        text = 'RFC Published'
        if doc.draft_name:
            try:
                text = 'RFC Published (see <a href="%s">%s</a> for earlier history)' % (urlreverse('doc_view', args=[doc.draft_name]),doc.draft_name)
            except NoReverseMatch:
                pass
        results.append({'is_text':True, 'date':doc.publication_date, 'text':text})

    # convert plain dates to datetimes (required for sorting)
    for x in results:
        if not isinstance(x['date'], datetime.datetime):
            if x['date']:
                x['date'] = datetime.datetime.combine(x['date'], datetime.time(0,0,0))
            else:
                x['date'] = datetime.datetime(1970,1,1)

    results.sort(key=lambda x: x['date'])
    results.reverse()
    return results

# takes InternetDraft instance
def _get_versions(draft, include_replaced=True):
    ov = []
    ov.append({"draft_name":draft.filename, "revision":draft.revision_display(), "date":draft.revision_date})
    if include_replaced:
        draft_list = [draft]+list(draft.replaces_set.all())
    else:
        draft_list = [draft]

    if settings.USE_DB_REDESIGN_PROXY_CLASSES:
        from ietf.doc.models import NewRevisionDocEvent
        for e in NewRevisionDocEvent.objects.filter(type="new_revision", doc__in=draft_list).select_related('doc').order_by("-time", "-id"):
            if not (e.doc.name == draft.name and e.rev == draft.rev):
                ov.append(dict(draft_name=e.doc.name, revision=e.rev, date=e.time.date()))
                
        return ov
        
    for d in draft_list:
        for v in DraftVersions.objects.filter(filename=d.filename).order_by('-revision'):
            if (d.filename == draft.filename) and (draft.revision_display() == v.revision):
                continue
            ov.append({"draft_name":d.filename, "revision":v.revision, "date":v.revision_date})
    return ov

def get_ballot(name):
    r = re.compile("^rfc([1-9][0-9]*)$")
    m = r.match(name)

    if settings.USE_DB_REDESIGN_PROXY_CLASSES:
        from ietf.doc.models import DocAlias
        alias = get_object_or_404(DocAlias, name=name)
        d = get_object_or_404(InternetDraft, name=alias.document.name)
        try:
            if not d.ballot.ballot_issued:
                raise Http404
        except BallotInfo.DoesNotExist:
            raise Http404

        bw = BallotWrapper(d)
        if m:
            d.viewing_as_rfc = True
            dw = RfcWrapper(d)
        else:
            dw = IdWrapper(d)

        return (bw, dw)
        
    if m:
        rfc_number = int(m.group(1))
        rfci = get_object_or_404(RfcIndex, rfc_number=rfc_number)
        id = get_object_or_404(IDInternal, rfc_flag=1, draft=rfc_number)
        doc = RfcWrapper(rfci, idinternal=id)
    else:
        id = get_object_or_404(IDInternal, rfc_flag=0, draft__filename=name)
        doc = IdWrapper(id) 
    try:
        if not id.ballot.ballot_issued:
            raise Http404
    except BallotInfo.DoesNotExist:
        raise Http404

    ballot = BallotWrapper(id)
    return ballot, doc

def ballot_html(request, name):
    ballot, doc = get_ballot(name)
    return render_to_response('idrfc/doc_ballot.html', {'ballot':ballot, 'doc':doc}, context_instance=RequestContext(request))

def ballot_tsv(request, name):
    ballot, doc = get_ballot(name)
    return HttpResponse(render_to_string('idrfc/ballot.tsv', {'ballot':ballot}, RequestContext(request)), content_type="text/plain")

def ballot_json(request, name):
    ballot, doc = get_ballot(name)
    response = HttpResponse(mimetype='text/plain')
    response.write(json.dumps(ballot.dict(), indent=2))
    return response

