# helpers for handling last calls on Internet Drafts

import datetime

from django.conf import settings

from ietf.idtracker.models import InternetDraft, DocumentComment, BallotInfo
from ietf.idrfc.mails import *
from ietf.idrfc.utils import *

from ietf.doc.models import Document, DocEvent, LastCallDocEvent, WriteupDocEvent, save_document_in_history, State
from ietf.person.models import Person

def request_last_call(request, doc):
    try:
        ballot = doc.idinternal.ballot
    except BallotInfo.DoesNotExist:
        ballot = generate_ballot(request, doc)

    send_last_call_request(request, doc, ballot)
    add_document_comment(request, doc, "Last Call was requested")

def request_last_callREDESIGN(request, doc):
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

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    request_last_call = request_last_callREDESIGN

def get_expired_last_calls():
    return InternetDraft.objects.filter(lc_expiration_date__lte=datetime.date.today(),
                                        idinternal__cur_state__document_state_id=IDState.IN_LAST_CALL)

def get_expired_last_callsREDESIGN():
    today = datetime.date.today()
    for d in Document.objects.filter(states__type="draft-iesg", states__slug="lc"):
        e = d.latest_event(LastCallDocEvent, type="sent_last_call")
        if e and e.expires.date() <= today:
            yield d

def expire_last_call(doc):
    state = IDState.WAITING_FOR_WRITEUP

    try:
        ballot = doc.idinternal.ballot
        if ballot.ballot_writeup and "What does this protocol do and why" not in ballot.ballot_writeup:
            state = IDState.WAITING_FOR_AD_GO_AHEAD
    except BallotInfo.DoesNotExist:
        pass

    doc.idinternal.change_state(IDState.objects.get(document_state_id=state), None)
    doc.idinternal.event_date = datetime.date.today()
    doc.idinternal.save()

    log_state_changed(None, doc, by="system", email_watch_list=False)

    email_last_call_expired(doc)

def expire_last_callREDESIGN(doc):
    state = State.objects.get(type="draft-iesg", slug="writeupw")

    e = doc.latest_event(WriteupDocEvent, type="changed_ballot_writeup_text")
    if e and "What does this protocol do and why" not in e.text:
        # if boiler-plate text has been removed, we assume the
        # write-up has been written
        state = State.objects.get(type="draft-iesg", slug="goaheadw")

    save_document_in_history(doc)

    prev = doc.get_state("draft-iesg")
    doc.set_state(state)

    prev_tag = doc.tags.filter(slug__in=('point', 'ad-f-up', 'need-rev', 'extpty'))
    prev_tag = prev_tag[0] if prev_tag else None
    if prev_tag:
        doc.tags.remove(prev_tag)

    e = log_state_changed(None, doc, Person.objects.get(name="(System)"), prev, prev_tag)
                    
    doc.time = e.time
    doc.save()

    email_last_call_expired(doc)

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    get_expired_last_calls = get_expired_last_callsREDESIGN
    expire_last_call = expire_last_callREDESIGN

