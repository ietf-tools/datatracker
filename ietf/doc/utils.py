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
        res.append("draft-iana-review")
        res.append("draft-iana-action")
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

# This, and several other utilities here, assume that there is only one active ballot for a document at any point in time.
# If that assumption is violated, they will only expose the most recently created ballot
def active_ballot(doc):
    """Returns the most recently created ballot if it isn't closed."""
    ballot = doc.latest_event(BallotDocEvent, type="created_ballot")
    open = ballot_open(doc,ballot.ballot_type.slug) if ballot else False
    return ballot if open else None
     

def active_ballot_positions(doc, ballot=None):
    """Return dict mapping each active AD to a current ballot position (or None if they haven't voted)."""
    active_ads = list(Person.objects.filter(role__name="ad", role__group__state="active"))
    res = {}

    if not ballot:
        ballot = doc.latest_event(BallotDocEvent, type="created_ballot")
    positions = BallotPositionDocEvent.objects.filter(doc=doc, type="changed_ballot_position", ad__in=active_ads, ballot=ballot).select_related('ad', 'pos').order_by("-time", "-id")

    for pos in positions:
        if pos.ad not in res:
            res[pos.ad] = pos

    for ad in active_ads:
        if ad not in res:
            res[ad] = None

    return res

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
    
def ballot_open(doc, ballot_type_slug):
    e = doc.latest_event(BallotDocEvent, ballot_type__slug=ballot_type_slug)
    return e and not e.type == "closed_ballot"

def create_ballot_if_not_open(doc, by, ballot_type_slug):
    if not ballot_open(doc, ballot_type_slug):
        e = BallotDocEvent(type="created_ballot", by=by, doc=doc)
        e.ballot_type = BallotType.objects.get(doc_type=doc.type, slug=ballot_type_slug)
        e.desc = u'Created "%s" ballot' % e.ballot_type.name
        e.save()

def close_open_ballots(doc, by):
    for t in BallotType.objects.filter(doc_type=doc.type_id):
        if ballot_open(doc, t.slug):
            e = BallotDocEvent(type="closed_ballot", doc=doc, by=by)
            e.ballot_type = t
            e.desc = 'Closed "%s" ballot' % t.name
            e.save()

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
    e = DocEvent(doc=doc, by=by)
    e.type = "changed_document"
    e.desc = u"State changed to <b>%s</b> from %s" % (new_description, old_description)
    e.save()
    return e

def add_state_change_event(doc, by, prev_state, new_state, timestamp=None):
    """Add doc event to explain that state change just happened."""
    if prev_state == new_state:
        return None

    e = StateDocEvent(doc=doc, by=by)
    e.type = "changed_state"
    e.state_type = (prev_state or new_state).type
    e.state = new_state
    e.desc = "%s changed to <b>%s</b>" % (e.state_type.label, new_state.name)
    if prev_state:
        e.desc += " from %s" % prev_state.name
    if timestamp:
        e.time = timestamp
    e.save()
    return e
    
