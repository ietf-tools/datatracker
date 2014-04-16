# utilities for constructing agendas for IESG telechats

import codecs
import datetime
from collections import OrderedDict

from django.conf import settings
from django.http import Http404

from ietf.doc.models import Document, TelechatDocEvent, LastCallDocEvent, ConsensusDocEvent
from ietf.iesg.models import TelechatDate, TelechatAgendaItem


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
        if doc.get_state_slug() != "rfc" and doc.get_state_slug('draft-iesg') not in ("lc", "writeupw", "goaheadw", "iesg-eva", "defer"):
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
            if relation.relationship.slug in ('tops','tois') or relation.target.document.std_level.slug in ('std','ds','ps'):
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
        if doc.get_state('conflrev').slug not in ('adrev','iesgeval','appr-reqnopub-pend','appr-reqnopub-sent','appr-noprob-pend','appr-noprob-sent','defer'):
             s = "3.4.3"
        elif doc.returning_item():
             s = "3.4.2"
        else:
             s = "3.4.1"

    return s

def agenda_sections():
    return OrderedDict([
        ('1', {'title':"Administrivia"}),
        ('1.1', {'title':"Roll Call"}),
        ('1.2', {'title':"Bash the Agenda"}),
        ('1.3', {'title':"Approval of the Minutes of Past Telechats"}),
        ('1.4', {'title':"List of Remaining Action Items from Last Telechat"}),
        ('2', {'title':"Protocol Actions"}),
        ('2.1', {'title':"WG Submissions"}),
        ('2.1.1', {'title':"New Items", 'docs': []}),
        ('2.1.2', {'title':"Returning Items", 'docs':[]}),
        ('2.1.3', {'title':"For Action", 'docs':[]}),
        ('2.2', {'title':"Individual Submissions"}),
        ('2.2.1', {'title':"New Items", 'docs':[]}),
        ('2.2.2', {'title':"Returning Items", 'docs':[]}),
        ('2.2.3', {'title':"For Action", 'docs':[]}),
        ('2.3', {'title':"Status Changes"}),
        ('2.3.1', {'title':"New Items", 'docs':[]}),
        ('2.3.2', {'title':"Returning Items", 'docs':[]}),
        ('2.3.3', {'title':"For Action", 'docs':[]}),
        ('3', {'title':"Document Actions"}),
        ('3.1', {'title':"WG Submissions"}),
        ('3.1.1', {'title':"New Items", 'docs':[]}),
        ('3.1.2', {'title':"Returning Items", 'docs':[]}),
        ('3.1.3', {'title':"For Action", 'docs':[]}),
        ('3.2', {'title':"Individual Submissions Via AD"}),
        ('3.2.1', {'title':"New Items", 'docs':[]}),
        ('3.2.2', {'title':"Returning Items", 'docs':[]}),
        ('3.2.3', {'title':"For Action", 'docs':[]}),
        ('3.3', {'title':"Status Changes"}),
        ('3.3.1', {'title':"New Items", 'docs':[]}),
        ('3.3.2', {'title':"Returning Items", 'docs':[]}),
        ('3.3.3', {'title':"For Action", 'docs':[]}),
        ('3.4', {'title':"IRTF and Independent Submission Stream Documents"}),
        ('3.4.1', {'title':"New Items", 'docs':[]}),
        ('3.4.2', {'title':"Returning Items", 'docs':[]}),
        ('3.4.3', {'title':"For Action", 'docs':[]}),
        ('4', {'title':"Working Group Actions"}),
        ('4.1', {'title':"WG Creation"}),
        ('4.1.1', {'title':"Proposed for IETF Review", 'docs':[]}),
        ('4.1.2', {'title':"Proposed for Approval", 'docs':[]}),
        ('4.2', {'title':"WG Rechartering"}),
        ('4.2.1', {'title':"Under Evaluation for IETF Review", 'docs':[]}),
        ('4.2.2', {'title':"Proposed for Approval", 'docs':[]}),
        ('5', {'title':"IAB News We Can Use"}),
        ('6', {'title':"Management Issues"}),
        ('7', {'title':"Working Group News"}),
        ])

def fill_in_agenda_administrivia(date, sections):
    extra_info_files = (
        ("1.1", "roll_call", settings.IESG_ROLL_CALL_FILE),
        ("1.3", "minutes", settings.IESG_MINUTES_FILE),
        ("1.4", "action_items", settings.IESG_TASK_FILE),
        )

    for s, key, filename in extra_info_files:
        try:
            with codecs.open(filename, 'r', 'utf-8', 'replace') as f:
                t = f.read().strip()
        except IOError:
            t = u"(Error reading %s)" % filename

        sections[s]["text"] = t

def fill_in_agenda_docs(date, sections, matches=None):
    if not matches:
        matches = Document.objects.filter(docevent__telechatdocevent__telechat_date=date)
        matches = matches.select_related("stream", "group").distinct()

    for doc in matches:
        if doc.latest_event(TelechatDocEvent, type="scheduled_for_telechat").telechat_date != date:
            continue

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
        elif doc.type_id == "conflrev":
            doc.conflictdoc = doc.relateddocument_set.get(relationship__slug='conflrev').target.document
        elif doc.type_id == "charter":
            #if doc.group.state_id not in ("proposed", "active"):
            #    continue

            doc.group.txt_link = settings.CHARTER_TXT_URL + "%s-%s.txt" % (doc.canonical_name(), doc.rev)

        number = get_doc_section(doc)
        if number: #  and num in sections
            sections[number]["docs"].append(doc)

    # prune empty "For action" sections
    empty_for_action = [n for n, section in sections.iteritems()
                        if section["title"] == "For Action" and not section["docs"]]
    for num in empty_for_action:
        del sections[num]

    # Be careful to keep this the same as what's used in agenda_documents
    for s in sections.itervalues():
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

