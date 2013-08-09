from django.conf import settings

from ietf.idrfc.mails import *
from ietf.ietfauth.utils import has_role, is_authorized_in_doc_stream

def add_document_comment(request, doc, text, ballot=None):
    if request:
        login = IESGLogin.objects.get(login_name=request.user.username)
    else:
        login = None

    c = DocumentComment()
    c.document = doc.idinternal
    c.public_flag = True
    c.version = doc.revision_display()
    c.comment_text = text
    c.created_by = login
    if ballot:
        c.ballot = ballot
    c.rfc_flag = doc.idinternal.rfc_flag
    c.save()

def generate_ballot(request, doc):
    ballot = BallotInfo()
    ballot.ballot = doc.idinternal.ballot_id
    ballot.active = False
    ballot.last_call_text = generate_last_call_announcement(request, doc)
    ballot.approval_text = generate_approval_mail(request, doc)
    ballot.ballot_writeup = render_to_string("idrfc/ballot_writeup.txt")
    ballot.save()
    doc.idinternal.ballot = ballot
    return ballot
    
def log_state_changed(request, doc, by, prev_iesg_state, prev_iesg_tag):
    from ietf.doc.models import DocEvent, IESG_SUBSTATE_TAGS

    state = doc.get_state("draft-iesg")

    state_name = state.name
    tags = doc.tags.filter(slug__in=IESG_SUBSTATE_TAGS)
    if tags:
        state_name += "::" + tags[0].name

    prev_state_name = prev_iesg_state.name if prev_iesg_state else "I-D Exists"
    if prev_iesg_tag:
        prev_state_name += "::" + prev_iesg_tag.name

    e = DocEvent(doc=doc, by=by)
    e.type = "changed_document"
    e.desc = u"State changed to <b>%s</b> from %s" % (state_name, prev_state_name)
    e.save()
    return e

def update_telechat(request, doc, by, new_telechat_date, new_returning_item=None):
    from ietf.doc.models import TelechatDocEvent
    
    on_agenda = bool(new_telechat_date)

    prev = doc.latest_event(TelechatDocEvent, type="scheduled_for_telechat")
    prev_returning = bool(prev and prev.returning_item)
    prev_telechat = prev.telechat_date if prev else None
    prev_agenda = bool(prev_telechat)
    
    returning_item_changed = bool(new_returning_item != None and new_returning_item != prev_returning)

    if new_returning_item == None:
        returning = prev_returning
    else:
        returning = new_returning_item

    if returning == prev_returning and new_telechat_date == prev_telechat:
        # fully updated, nothing to do
        return

    # auto-update returning item
    if (not returning_item_changed and on_agenda and prev_agenda
        and new_telechat_date != prev_telechat):
        returning = True

    e = TelechatDocEvent()
    e.type = "scheduled_for_telechat"
    e.by = by
    e.doc = doc
    e.returning_item = returning
    e.telechat_date = new_telechat_date
    
    if on_agenda != prev_agenda:
        if on_agenda:
            e.desc = "Placed on agenda for telechat - %s" % (new_telechat_date)
        else:
            e.desc = "Removed from agenda for telechat"
    elif on_agenda and new_telechat_date != prev_telechat:
        e.desc = "Telechat date has been changed to <b>%s</b> from <b>%s</b>" % (
            new_telechat_date, prev_telechat)
    else:
        # we didn't reschedule but flipped returning item bit - let's
        # just explain that
        if returning:
            e.desc = "Set telechat returning item indication"
        else:
            e.desc = "Removed telechat returning item indication"

    e.save()
