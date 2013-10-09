# utilities for constructing agendas for IESG telechats

import codecs, re, os, datetime

from django.http import Http404
from django.conf import settings

from ietf.iesg.models import TelechatDate, TelechatAgendaItem
from ietf.doc.models import Document, TelechatDocEvent, LastCallDocEvent, ConsensusDocEvent, DocEvent
from ietf.group.models import Group, GroupMilestone

def get_agenda_date(date=None):
    if not date:
        try:
            return TelechatDate.objects.active().order_by('date')[0].date
        except IndexError:
            return datetime.date.today()
    else:
        try:
            return TelechatDate.objects.active().get(date=datetime.datetime.strptime(date, "%Y-%m-%d").date()).date
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
            s = s + "1"
        elif (s == "3") and doc.stream_id in ("ise","irtf"):
            s = s + "3"
        else:
            s = s + "2"
        if doc.get_state_slug() != "rfc" and doc.get_state_slug('draft-iesg') not in ("lc", "writeupw", "goaheadw", "iesg-eva", "defer"):
            s = s + "3"
        elif doc.returning_item():
            s = s + "2"
        else:
            s = s + "1"
    elif doc.type_id == 'charter':
        s = get_wg_section(doc.group)
    elif doc.type_id == 'statchg':
        protocol_action = False
        for relation in doc.relateddocument_set.filter(relationship__slug__in=('tops','tois','tohist','toinf','tobcp','toexp')):
            if relation.relationship.slug in ('tops','tois') or relation.target.document.std_level.slug in ('std','ds','ps'):
                protocol_action = True
        if protocol_action:
            s="23"
        else:
            s="33"
        if doc.get_state_slug() not in ("iesgeval", "defer", "appr-pr", "appr-pend", "appr-sent"):
            s = s + "3"
        elif doc.returning_item():
            s = s + "2"
        else:
            s = s + "1"
    elif doc.type_id == 'conflrev':
        if doc.get_state('conflrev').slug not in ('adrev','iesgeval','appr-reqnopub-pend','appr-reqnopub-sent','appr-noprob-pend','appr-noprob-sent','defer'):
             s = "343"
        elif doc.returning_item():
             s = "342"
        else:
             s = "341"

    return s

def get_wg_section(wg):
    s = ""
    charter_slug = None
    if wg.charter:
        charter_slug = wg.charter.get_state_slug()
    if wg.state_id in ['active','dormant']:
        if charter_slug in ['extrev','iesgrev']:
            s = '422'
        else:
            s = '421'
    else:
        if charter_slug in ['extrev','iesgrev']:
            s = '412'
        else:
            s = '411'
    return s

def agenda_docs(date):
    matches = Document.objects.filter(docevent__telechatdocevent__telechat_date=date).select_related("stream").distinct()

    docmatches = []
        
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
                if e:
                    doc.consensus = "Yes" if e.consensus else "No"
        elif doc.type_id=='conflrev':
            doc.conflictdoc = doc.relateddocument_set.get(relationship__slug='conflrev').target.document

        docmatches.append(doc)

    # Be careful to keep this the same as what's used in agenda_documents
    docmatches.sort(key=lambda d: d.balloting_started)
    
    res = dict(("s%s%s%s" % (i, j, k), []) for i in range(2, 5) for j in range (1, 4) for k in range(1, 4))
    for k in range(1,4):
        res['s34%d'%k]=[]
    for doc in docmatches:
        section_key = "s" + get_doc_section(doc)
        if section_key not in res:
            res[section_key] = []
        res[section_key].append(doc)
    return res

def agenda_wg_actions(date):
    res = dict(("s%s%s%s" % (i, j, k), []) for i in range(2, 5) for j in range (1, 4) for k in range(1, 4))
    charters = Document.objects.filter(type="charter", docevent__telechatdocevent__telechat_date=date).select_related("group").distinct()
    charters = charters.filter(group__state__slug__in=["proposed","active"])
    for c in charters:
        if c.latest_event(TelechatDocEvent, type="scheduled_for_telechat").telechat_date != date:
            continue

        c.group.txt_link = settings.CHARTER_TXT_URL + "%s-%s.txt" % (c.canonical_name(), c.rev)

        section_key = "s" + get_wg_section(c.group)
        if section_key not in res:
            res[section_key] = []
        res[section_key].append(c)
    return res

def agenda_management_issues(date):
    return TelechatAgendaItem.objects.filter(type=3).order_by('id')

def agenda_data(request, date=None):
    """Return a dict with the different IESG telechat agenda components."""
    date = get_agenda_date(date)
    docs = agenda_docs(date)
    mgmt = agenda_management_issues(date)
    wgs = agenda_wg_actions(date)
    data = {'date':str(date), 'docs':docs,'mgmt':mgmt,'wgs':wgs}
    for key, filename in {'action_items':settings.IESG_TASK_FILE,
                          'roll_call':settings.IESG_ROLL_CALL_FILE,
                          'minutes':settings.IESG_MINUTES_FILE}.items():
        try:
            f = codecs.open(filename, 'r', 'utf-8', 'replace')
            text = f.read().strip()
            f.close()
            data[key] = text
        except IOError:
            data[key] = "(Error reading "+key+")"
    return data

