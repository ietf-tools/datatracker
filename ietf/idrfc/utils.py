from ietf.idtracker.models import InternetDraft, DocumentComment, BallotInfo, IESGLogin
from ietf.idrfc.mails import *

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
    
def log_state_changed(request, doc, by, email_watch_list=True, note=''):
    change = u"State changed to <b>%s</b> from %s." % (
        doc.idinternal.docstate(),
        format_document_state(doc.idinternal.prev_state,
                              doc.idinternal.prev_sub_state))
    if note:
        change += "<br>%s" % note

    c = DocumentComment()
    c.document = doc.idinternal
    c.public_flag = True
    c.version = doc.revision_display()
    c.comment_text = change

    if doc.idinternal.docstate()=="In Last Call":
        c.comment_text += "\n\n<b>The following Last Call Announcement was sent out:</b>\n\n"
        c.comment_text += doc.idinternal.ballot.last_call_text


    if isinstance(by, IESGLogin):
        c.created_by = by
    c.result_state = doc.idinternal.cur_state
    c.origin_state = doc.idinternal.prev_state
    c.rfc_flag = doc.idinternal.rfc_flag
    c.save()

    if email_watch_list:
        email_state_changed(request, doc, strip_tags(change))

    return change

       
def update_telechat(request, idinternal, new_telechat_date, new_returning_item=None):
    on_agenda = bool(new_telechat_date)

    if new_returning_item == None:
        new_returning_item = idinternal.returning_item
    
    returning_item_changed = False
    if idinternal.returning_item != bool(new_returning_item):
        idinternal.returning_item = bool(new_returning_item)
        returning_item_changed = True

    # auto-update returning item
    if (not returning_item_changed and
        on_agenda and idinternal.agenda
        and new_telechat_date != idinternal.telechat_date):
        idinternal.returning_item = True

    # update agenda
    doc = idinternal.document()
    if bool(idinternal.agenda) != on_agenda:
        if on_agenda:
            add_document_comment(request, doc,
                                 "Placed on agenda for telechat - %s" % new_telechat_date)
            idinternal.telechat_date = new_telechat_date
        else:
            add_document_comment(request, doc,
                                 "Removed from agenda for telechat")
        idinternal.agenda = on_agenda
    elif on_agenda and new_telechat_date != idinternal.telechat_date:
        add_document_comment(request, doc,
                             "Telechat date has been changed to <b>%s</b> from <b>%s</b>" %
                             (new_telechat_date,
                              idinternal.telechat_date))
        idinternal.telechat_date = new_telechat_date
