# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-


# utilities for constructing agendas for IESG telechats

import io
import datetime
from collections import OrderedDict

from django.conf import settings
from django.http import Http404

import debug                            # pyflakes:ignore

from ietf.doc.models import Document, LastCallDocEvent, ConsensusDocEvent
from ietf.doc.utils_search import fill_in_telechat_date
from ietf.iesg.models import TelechatDate, TelechatAgendaItem
from ietf.review.utils import review_assignments_to_list_for_docs

def get_agenda_date(date=None):
    if not date:
        try:
            return TelechatDate.objects.active().order_by('date')[0].date
        except IndexError:
            return datetime.date.today()
    else:
        try:
            # FIXME: .active()
            return TelechatDate.objects.all().get(date=datetime.datetime.strptime(date, "%Y-%m-%d").date()).date
        except (ValueError, TelechatDate.DoesNotExist):
            raise Http404

def get_doc_section(doc):
    if doc.type_id == 'draft':
        if doc.intended_std_level_id in ["bcp", "ds", "ps", "std"]:
            s = "2"
        else:
            s = "3"

        g = doc.group_acronym()
        if g and str(g) != 'none':
            s += ".1"
        elif s == "3" and doc.stream_id in ("ise","irtf"):
            s += ".3"
        else:
            s += ".2"
        if doc.get_state_slug() != "rfc" and doc.get_state_slug('draft-iesg') not in ("lc", "writeupw", "goaheadw", "iesg-eva", "defer", "approved", "ann", "rfcqueue", "pub"):
            s += ".3"
        elif doc.returning_item():
            s += ".2"
        else:
            s += ".1"

    elif doc.type_id == 'charter':
        s = "4"
        if doc.group.state_id in ('active', 'dormant'):
            s += ".2"
        else:
            s += ".1"
        if doc.get_state_slug() in ('extrev', 'iesgrev'):
            s += '.2'
        else:
            s += '.1'

    elif doc.type_id == 'statchg':
        protocol_action = False
        for relation in doc.relateddocument_set.filter(relationship__slug__in=('tops','tois','tohist','toinf','tobcp','toexp')):
            if relation.relationship_id in ('tops','tois') or relation.target.document.std_level_id in ('std','ds','ps'):
                protocol_action = True
        if protocol_action:
            s = "2.3"
        else:
            s = "3.3"
        if doc.get_state_slug() not in ("iesgeval", "defer", "appr-pr", "appr-pend", "appr-sent"):
            s += ".3"
        elif doc.returning_item():
            s += ".2"
        else:
            s += ".1"

    elif doc.type_id == 'conflrev':
        if not doc.get_state('conflrev') or doc.get_state('conflrev').slug not in ('adrev','iesgeval','appr-reqnopub-pend','appr-reqnopub-sent','appr-noprob-pend','appr-noprob-sent','defer'):
             s = "3.4.3"
        elif doc.returning_item():
             s = "3.4.2"
        else:
             s = "3.4.1"

    return s

def agenda_sections():
    return OrderedDict([
        ('1', {'title':"Administrivia"}),
        ('1.1', {'title':"Roll call"}),
        ('1.2', {'title':"Bash the agenda"}),
        ('1.3', {'title':"Approval of the minutes of past telechats"}),
        ('1.4', {'title':"List of remaining action items from last telechat"}),
        ('2', {'title':"Protocol actions"}),
        ('2.1', {'title':"WG submissions"}),
        ('2.1.1', {'title':"New items", 'docs': []}),
        ('2.1.2', {'title':"Returning items", 'docs':[]}),
        ('2.1.3', {'title':"For action", 'docs':[]}),
        ('2.2', {'title':"Individual submissions"}),
        ('2.2.1', {'title':"New items", 'docs':[]}),
        ('2.2.2', {'title':"Returning items", 'docs':[]}),
        ('2.2.3', {'title':"For action", 'docs':[]}),
        ('2.3', {'title':"Status changes"}),
        ('2.3.1', {'title':"New items", 'docs':[]}),
        ('2.3.2', {'title':"Returning items", 'docs':[]}),
        ('2.3.3', {'title':"For action", 'docs':[]}),
        ('3', {'title':"Document actions"}),
        ('3.1', {'title':"WG submissions"}),
        ('3.1.1', {'title':"New items", 'docs':[]}),
        ('3.1.2', {'title':"Returning items", 'docs':[]}),
        ('3.1.3', {'title':"For action", 'docs':[]}),
        ('3.2', {'title':"Individual submissions via AD"}),
        ('3.2.1', {'title':"New items", 'docs':[]}),
        ('3.2.2', {'title':"Returning items", 'docs':[]}),
        ('3.2.3', {'title':"For action", 'docs':[]}),
        ('3.3', {'title':"Status changes"}),
        ('3.3.1', {'title':"New items", 'docs':[]}),
        ('3.3.2', {'title':"Returning items", 'docs':[]}),
        ('3.3.3', {'title':"For action", 'docs':[]}),
        ('3.4', {'title':"IRTF and Independent Submission stream documents"}),
        ('3.4.1', {'title':"New items", 'docs':[]}),
        ('3.4.2', {'title':"Returning items", 'docs':[]}),
        ('3.4.3', {'title':"For action", 'docs':[]}),
        ('4', {'title':"Working Group actions"}),
        ('4.1', {'title':"WG creation"}),
        ('4.1.1', {'title':"Proposed for IETF review", 'docs':[]}),
        ('4.1.2', {'title':"Proposed for approval", 'docs':[]}),
        ('4.2', {'title':"WG rechartering"}),
        ('4.2.1', {'title':"Under evaluation for IETF review", 'docs':[]}),
        ('4.2.2', {'title':"Proposed for approval", 'docs':[]}),
        ('5', {'title':"IAB news we can use"}),
        ('6', {'title':"Management issues"}),
        ('7', {'title':"Any Other Business (WG News, New Proposals, etc.)"}),
        ])

def fill_in_agenda_administrivia(date, sections):
    extra_info_files = (
        ("1.1", "roll_call", settings.IESG_ROLL_CALL_FILE),
        ("1.3", "minutes", settings.IESG_MINUTES_FILE),
        ("1.4", "action_items", settings.IESG_TASK_FILE),
        )

    for s, key, filename in extra_info_files:
        try:
            with io.open(filename, 'r', encoding='utf-8', errors='replace') as f:
                t = f.read().strip()
        except IOError:
            t = "(Error reading %s)" % filename

        sections[s]["text"] = t

def fill_in_agenda_docs(date, sections, docs=None):
    if not docs:
        docs = Document.objects.filter(docevent__telechatdocevent__telechat_date=date)
        docs = docs.select_related("stream", "group").distinct()
        fill_in_telechat_date(docs)

    review_assignments_for_docs = review_assignments_to_list_for_docs(docs)

    for doc in docs:
        if doc.telechat_date() != date:
            continue

        if not hasattr(doc, 'balloting_started'):
            e = doc.latest_event(type="started_iesg_process")
            doc.balloting_started = e.time if e else datetime.datetime.min

        if doc.type_id == "draft":
            s = doc.get_state("draft-iana-review")
            if s: # and s.slug in ("not-ok", "changed", "need-rev"):
                doc.iana_review_state = str(s)

            if doc.get_state_slug("draft-iesg") == "lc":
                e = doc.latest_event(LastCallDocEvent, type="sent_last_call")
                if e:
                    doc.lastcall_expires = e.expires

            if doc.stream_id in ("ietf", "irtf", "iab"):
                doc.consensus = "Unknown"
                e = doc.latest_event(ConsensusDocEvent, type="changed_consensus")
                if e and (e.consensus != None):
                    doc.consensus = "Yes" if e.consensus else "No"

            doc.review_assignments = review_assignments_for_docs.get(doc.name, [])
        elif doc.type_id == "conflrev":
            doc.conflictdoc = doc.relateddocument_set.get(relationship__slug='conflrev').target.document
        elif doc.type_id == "charter":
            pass

        number = get_doc_section(doc)
        if number: #  and num in sections
            sections[number]["docs"].append(doc)

    # prune empty "For action" sections
    empty_for_action = [n for n, section in sections.items()
                        if section["title"] == "For action" and not section["docs"]]
    for num in empty_for_action:
        del sections[num]

    # Be careful to keep this the same as what's used in agenda_documents
    for s in sections.values():
        if "docs" in s:
            s["docs"].sort(key=lambda d: d.balloting_started)

def fill_in_agenda_management_issues(date, sections):
    s = "6.%s"
    for i, item in enumerate(TelechatAgendaItem.objects.filter(type=3).order_by('id'), start=1):
        sections[s % i] = { "title": item.title, "text": item.text }

def agenda_data(date=None):
    """Return a dict with the different IESG telechat agenda components."""
    date = get_agenda_date(date)
    sections = agenda_sections()

    fill_in_agenda_administrivia(date, sections)
    fill_in_agenda_docs(date, sections)
    fill_in_agenda_management_issues(date, sections)

    return { 'date': date.isoformat(), 'sections': sections }

