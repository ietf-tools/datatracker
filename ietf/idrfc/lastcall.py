# helpers for handling last calls on Internet Drafts

import datetime

from ietf.idtracker.models import InternetDraft, DocumentComment, BallotInfo, IESGLogin
from ietf.idrfc.mails import *
from ietf.idrfc.utils import *

def request_last_call(request, doc):
    try:
        ballot = doc.idinternal.ballot
    except BallotInfo.DoesNotExist:
        ballot = generate_ballot(request, doc)

    send_last_call_request(request, doc, ballot)
    add_document_comment(request, doc, "Last Call was requested")

def get_expired_last_calls():
    return InternetDraft.objects.filter(lc_expiration_date__lte=datetime.date.today(),
                                        idinternal__cur_state__document_state_id=IDState.IN_LAST_CALL)

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
