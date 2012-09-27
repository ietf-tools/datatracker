import os
from django.conf import settings

# Should this move from idrfc to doc?
from ietf.idrfc import markup_txt

from ietf.doc.models import *

def get_state_types(doc):
    res = []

    if not doc:
        return res
    
    res.append(doc.type_id)

    if doc.type_id == "draft":
        if doc.stream_id and doc.stream_id != "legacy":
            res.append("draft-stream-%s" % doc.stream_id)

        res.append("draft-iesg")
        res.append("draft-iana")
        res.append("draft-rfceditor")
        
    return res

def get_tags_for_stream_id(stream_id):
    if stream_id == "ietf":
        return ["w-expert", "w-extern", "w-merge", "need-aut", "w-refdoc", "w-refing", "rev-wglc", "rev-ad", "rev-iesg", "sheph-u", "other"]
    elif stream_id == "iab":
        return ["need-ed", "w-part", "w-review", "need-rev", "sh-f-up"]
    elif stream_id == "irtf":
        return ["need-ed", "need-sh", "w-dep", "need-rev", "iesg-com"]
    elif stream_id == "ise":
        return ["w-dep", "w-review", "need-rev", "iesg-com"]
    else:
        return []

def needed_ballot_positions(doc, active_positions):
    '''Returns text answering the question "what does this document
    need to pass?".  The return value is only useful if the document
    is currently in IESG evaluation.'''
    yes = [p for p in active_positions if p and p.pos_id == "yes"]
    noobj = [p for p in active_positions if p and p.pos_id == "noobj"]
    blocking = [p for p in active_positions if p and p.pos.blocking]
    recuse = [p for p in active_positions if p and p.pos_id == "recuse"]

    answer = []
    if len(yes) < 1:
        answer.append("Needs a YES.")
    if blocking:
        if blocking:
            answer.append("Has a %s." % blocking[0].pos.name.upper())
        else:
            answer.append("Has %d %s." % (len(blocking), blocking[0].name.upper()))
    needed = 1
    if doc.type_id == "draft" and doc.intended_std_level_id in ("bcp", "ps", "ds", "std"):
        # For standards-track, need positions from 2/3 of the
        # non-recused current IESG.
        needed = (len(active_positions) - len(recuse)) * 2 // 3

    have = len(yes) + len(noobj) + len(blocking)
    if have < needed:
        more = needed - have
        if more == 1:
            answer.append("Needs %d more position." % more)
        else:
            answer.append("Needs %d more positions." % more)
    else:
        if blocking:
            answer.append("Has enough positions to pass once %s positions are resolved." % blocking[0].pos.name.upper())
        else:
            answer.append("Has enough positions to pass.")

    return " ".join(answer)
    
def create_ballot_if_not_open(doc, by, ballot_slug):
    if not doc.ballot_open(ballot_slug):
        e = BallotDocEvent(type="created_ballot", by=by, doc=doc)
        e.ballot_type = BallotType.objects.get(doc_type=doc.type, slug=ballot_slug)
        e.desc = u'Created "%s" ballot' % e.ballot_type.name
        e.save()

def close_ballot(doc, by, ballot_slug):
    if doc.ballot_open(ballot_slug):
        e = BallotDocEvent(type="closed_ballot", doc=doc, by=by)
        e.ballot_type = BallotType.objects.get(doc_type=doc.type,slug=ballot_slug)
        e.desc = 'Closed "%s" ballot' % e.ballot_type.name
        e.save()

def close_open_ballots(doc, by):
    for t in BallotType.objects.filter(doc_type=doc.type_id):
        close_ballot(doc, by, t.slug )

def augment_with_start_time(docs):
    """Add a started_time attribute to each document with the time of
    the first revision."""
    docs = list(docs)

    docs_dict = {}
    for d in docs:
        docs_dict[d.pk] = d
        d.start_time = None

    seen = set()

    for e in DocEvent.objects.filter(type="new_revision", doc__in=docs).order_by('time'):
        if e.doc_id in seen:
            continue

        print e.time, e.doc_id

        docs_dict[e.doc_id].start_time = e.time
        seen.add(e.doc_id)

    return docs

def get_chartering_type(doc):
    chartering = ""
    if doc.get_state_slug() not in ("notrev", "approved"):
        if doc.group.state_id in ("proposed", "bof"):
            chartering = "initial"
        elif doc.group.state_id == "active":
            chartering = "rechartering"

    return chartering

def augment_events_with_revision(doc, events):
    """Take a set of events for doc and add a .rev attribute with the
    revision they refer to by checking NewRevisionDocEvents."""

    event_revisions = list(NewRevisionDocEvent.objects.filter(doc=doc).order_by('time', 'id').values('id', 'rev', 'time'))

    cur_rev = doc.rev
    if doc.get_state_slug() == "rfc":
        cur_rev = "RFC"

    for e in sorted(events, key=lambda e: (e.time, e.id), reverse=True):
        while event_revisions and (e.time, e.id) < (event_revisions[-1]["time"], event_revisions[-1]["id"]):
            event_revisions.pop()

        if event_revisions:
            cur_rev = event_revisions[-1]["rev"]
        else:
            cur_rev = "00"

        e.rev = cur_rev


def get_document_content(key, filename, split=True, markup=True):
    f = None
    try:
        f = open(filename, 'rb')
        raw_content = f.read()
    except IOError:
        error = "Error; cannot read ("+key+")"
        if split:
            return (error, "")
        else:
            return error
    finally:
        if f:
            f.close()
    if markup:
        return markup_txt.markup(raw_content,split)
    else:
        return raw_content

def log_state_changed(request, doc, by, new_description, old_description):
    from ietf.doc.models import DocEvent

    e = DocEvent(doc=doc, by=by)
    e.type = "changed_document"
    e.desc = u"State changed to <b>%s</b> from %s" % (new_description, old_description)
    e.save()
    return e

