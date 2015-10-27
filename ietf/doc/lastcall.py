# helpers for handling last calls on Internet Drafts

import datetime

from django.db.models import Q

from ietf.doc.models import Document, State, DocEvent, LastCallDocEvent, WriteupDocEvent
from ietf.doc.models import IESG_SUBSTATE_TAGS
from ietf.person.models import Person
from ietf.doc.utils import add_state_change_event
from ietf.doc.mails import generate_ballot_writeup, generate_approval_mail, generate_last_call_announcement
from ietf.doc.mails import send_last_call_request, email_last_call_expired

def request_last_call(request, doc):
    if not doc.latest_event(type="changed_ballot_writeup_text"):
        e = generate_ballot_writeup(request, doc)
        e.save()
    if not doc.latest_event(type="changed_ballot_approval_text"):
        e = generate_approval_mail(request, doc)
        e.save()
    if not doc.latest_event(type="changed_last_call_text"):
        e = generate_last_call_announcement(request, doc)
        e.save()

    send_last_call_request(request, doc)
    
    e = DocEvent()
    e.type = "requested_last_call"
    e.by = request.user.person
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
        new_state = State.objects.get(used=True, type="draft-iesg", slug="writeupw")
        e = doc.latest_event(WriteupDocEvent, type="changed_ballot_writeup_text")
        if e and "Relevant content can frequently be found in the abstract" not in e.text:
            # if boiler-plate text has been removed, we assume the
            # write-up has been written
            new_state = State.objects.get(used=True, type="draft-iesg", slug="goaheadw")
    elif doc.type_id == 'statchg':
        new_state = State.objects.get(used=True, type="statchg", slug="goahead")
    else:
        raise ValueError("Unexpected document type to expire_last_call(): %s" % doc.type)

    prev_state = doc.get_state(new_state.type_id)
    doc.set_state(new_state)

    prev_tags = doc.tags.filter(slug__in=IESG_SUBSTATE_TAGS)
    doc.tags.remove(*prev_tags)

    system = Person.objects.get(name="(System)")
    e = add_state_change_event(doc, system, prev_state, new_state, prev_tags=prev_tags, new_tags=[])
    if e:
        doc.save_with_history([e])

    email_last_call_expired(doc)
