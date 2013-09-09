# helpers for handling last calls on Internet Drafts

import datetime

from django.conf import settings

from ietf.doc.models import *
from ietf.person.models import Person
from ietf.doc.utils import log_state_changed
from ietf.doc.mails import *

def request_last_call(request, doc):
    if not doc.latest_event(type="changed_ballot_writeup_text"):
        generate_ballot_writeup(request, doc)
    if not doc.latest_event(type="changed_ballot_approval_text"):
        generate_approval_mail(request, doc)
    if not doc.latest_event(type="changed_last_call_text"):
        generate_last_call_announcement(request, doc)
    
    send_last_call_request(request, doc)
    
    e = DocEvent()
    e.type = "requested_last_call"
    e.by = request.user.get_profile()
    e.doc = doc
    e.desc = "Last call was requested"
    e.save()

def get_expired_last_calls():
    today = datetime.date.today()
    for d in Document.objects.filter(Q(states__type="draft-iesg", states__slug="lc")
                                    | Q(states__type="statchg", states__slug="in-lc")):
        e = d.latest_event(LastCallDocEvent, type="sent_last_call")
        if e and e.expires.date() <= today:
            yield d

def expire_last_call(doc):
    if doc.type_id == 'draft':
        state = State.objects.get(used=True, type="draft-iesg", slug="writeupw")
        e = doc.latest_event(WriteupDocEvent, type="changed_ballot_writeup_text")
        if e and "Relevant content can frequently be found in the abstract" not in e.text:
            # if boiler-plate text has been removed, we assume the
            # write-up has been written
            state = State.objects.get(used=True, type="draft-iesg", slug="goaheadw")
        prev = doc.get_state("draft-iesg")
    elif doc.type_id == 'statchg':
        state = State.objects.get(used=True, type="statchg", slug="goahead")
        prev = doc.get_state("statchg")
    else:
        raise ValueError("Unexpected document type to expire_last_call(): %s" % doc.type)

    prev_state = doc.friendly_state()

    save_document_in_history(doc)
    doc.set_state(state)

    prev_tag = doc.tags.filter(slug__in=IESG_SUBSTATE_TAGS)
    prev_tag = prev_tag[0] if prev_tag else None
    if prev_tag:
        doc.tags.remove(prev_tag)

    e = log_state_changed(None, doc, Person.objects.get(name="(System)"), doc.friendly_state(), prev_state)
                    
    doc.time = e.time
    doc.save()

    email_last_call_expired(doc)
