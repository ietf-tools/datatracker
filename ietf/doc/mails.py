# generation of mails 

import os
import textwrap, datetime

from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.core.urlresolvers import reverse as urlreverse

from ietf.utils.mail import send_mail, send_mail_text
from ietf.ipr.utils import iprs_from_docs, related_docs
from ietf.doc.models import WriteupDocEvent, LastCallDocEvent, DocAlias, ConsensusDocEvent
from ietf.doc.utils import needed_ballot_positions, get_document_content
from ietf.group.models import Role
from ietf.doc.models import Document
from ietf.mailtrigger.utils import gather_address_lists

def email_state_changed(request, doc, text, mailtrigger_id=None):
    (to,cc) = gather_address_lists(mailtrigger_id or 'doc_state_edited',doc=doc)
    if not to:
        return
    
    text = strip_tags(text)
    send_mail(request, to, None,
              "ID Tracker State Update Notice: %s" % doc.file_tag(),
              "doc/mail/state_changed_email.txt",
              dict(text=text,
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url()),
              cc=cc)

def email_stream_changed(request, doc, old_stream, new_stream, text=""):
    """Email the change text to the notify group and to the stream chairs"""
    streams = []
    if old_stream:
        streams.append(old_stream.slug)
    if new_stream:
        streams.append(new_stream.slug)
    (to,cc) = gather_address_lists('doc_stream_changed',doc=doc,streams=streams)

    if not to:
        return
    
    if not text:
        text = u"Stream changed to <b>%s</b> from %s" % (new_stream, old_stream)
    text = strip_tags(text)

    send_mail(request, to, None,
              "ID Tracker Stream Change Notice: %s" % doc.file_tag(),
              "doc/mail/stream_changed_email.txt",
              dict(text=text,
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url()),
              cc=cc)

def email_pulled_from_rfc_queue(request, doc, comment, prev_state, next_state):
    extra=extra_automation_headers(doc)
    addrs = gather_address_lists('doc_pulled_from_rfc_queue',doc=doc)
    extra['Cc'] = addrs.as_strings().cc
    send_mail(request, addrs.to , None,
              "%s changed state from %s to %s" % (doc.name, prev_state.name, next_state.name),
              "doc/mail/pulled_from_rfc_queue_email.txt",
              dict(doc=doc,
                   prev_state=prev_state,
                   next_state=next_state,
                   comment=comment,
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url()),
              extra=extra)

def email_iesg_processing_document(request, doc, changes):
    addrs = gather_address_lists('doc_iesg_processing_started',doc=doc)
    send_mail(request, addrs.to, None,
              'IESG processing details changed for %s' % doc.name,
              'doc/mail/email_iesg_processing.txt', 
              dict(doc=doc,
                   changes=changes),
              cc=addrs.cc)

def html_to_text(html):
    return strip_tags(html.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").replace("<br>", "\n"))
    
def generate_ballot_writeup(request, doc):
    e = doc.latest_event(type="iana_review")
    iana = e.desc if e else ""

    e = WriteupDocEvent()
    e.type = "changed_ballot_writeup_text"
    e.by = request.user.person
    e.doc = doc
    e.desc = u"Ballot writeup was generated"
    e.text = unicode(render_to_string("doc/mail/ballot_writeup.txt", {'iana': iana}))
    e.save()
    
    return e
    
def generate_last_call_announcement(request, doc):
    expiration_date = datetime.date.today() + datetime.timedelta(days=14)
    if doc.group.type_id in ("individ", "area"):
        group = "an individual submitter"
        expiration_date += datetime.timedelta(days=14)
    else:
        group = "the %s WG (%s)" % (doc.group.name, doc.group.acronym)

    doc.filled_title = textwrap.fill(doc.title, width=70, subsequent_indent=" " * 3)
    
    iprs = iprs_from_docs(related_docs(DocAlias.objects.get(name=doc.canonical_name())))
    if iprs:
        ipr_links = [ urlreverse("ietf.ipr.views.show", kwargs=dict(id=i.id)) for i in iprs]
        ipr_links = [ settings.IDTRACKER_BASE_URL+url if not url.startswith("http") else url for url in ipr_links ]
    else:
        ipr_links = None


    addrs = gather_address_lists('last_call_issued',doc=doc).as_strings()
    mail = render_to_string("doc/mail/last_call_announcement.txt",
                            dict(doc=doc,
                                 doc_url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url() + "ballot/",
                                 expiration_date=expiration_date.strftime("%Y-%m-%d"), #.strftime("%B %-d, %Y"),
                                 to=addrs.to,
                                 cc=addrs.cc,
                                 group=group,
                                 docs=[ doc ],
                                 urls=[ settings.IDTRACKER_BASE_URL + doc.get_absolute_url() ],
                                 ipr_links=ipr_links,
                                 )
                            )

    e = WriteupDocEvent()
    e.type = "changed_last_call_text"
    e.by = request.user.person
    e.doc = doc
    e.desc = u"Last call announcement was generated"
    e.text = unicode(mail)
    e.save()

    return e
    

DO_NOT_PUBLISH_IESG_STATES = ("nopubadw", "nopubanw")

def generate_approval_mail(request, doc):
    if doc.get_state_slug("draft-iesg") in DO_NOT_PUBLISH_IESG_STATES or doc.stream_id in ('ise','irtf'):
        mail = generate_approval_mail_rfc_editor(request, doc)
    else:
        mail = generate_approval_mail_approved(request, doc)

    e = WriteupDocEvent()
    e.type = "changed_ballot_approval_text"
    e.by = request.user.person
    e.doc = doc
    e.desc = u"Ballot approval text was generated"
    e.text = unicode(mail)
    e.save()

    return e

def generate_approval_mail_approved(request, doc):

    if doc.intended_std_level_id in ("std", "ds", "ps", "bcp"):
        action_type = "Protocol"
    else:
        action_type = "Document"

    # the second check catches some area working groups (like
    # Transport Area Working Group)
    if doc.group.type_id not in ("area", "individ", "ag") and not doc.group.name.endswith("Working Group"):
        doc.group.name_with_wg = doc.group.name + " Working Group"
    else:
        doc.group.name_with_wg = doc.group.name

    doc.filled_title = textwrap.fill(doc.title, width=70, subsequent_indent=" " * 3)

    if doc.group.type_id in ("individ", "area"):
        made_by = "This document has been reviewed in the IETF but is not the product of an IETF Working Group."
    else:
        made_by = "This document is the product of the %s." % doc.group.name_with_wg
    
    responsible_directors = set([doc.ad,])
    if doc.group.type_id not in ("individ","area"):
        responsible_directors.update([x.person for x in Role.objects.filter(group=doc.group.parent,name='ad')])
    responsible_directors = [x.plain_name() for x in responsible_directors if x]
    
    if len(responsible_directors)>1:
        contacts = "The IESG contact persons are "+", ".join(responsible_directors[:-1])+" and "+responsible_directors[-1]+"."
    else:
        contacts = "The IESG contact person is %s." % responsible_directors[0]

    doc_type = "RFC" if doc.get_state_slug() == "rfc" else "Internet Draft"
        
    addrs = gather_address_lists('ballot_approved_ietf_stream',doc=doc).as_strings()
    return render_to_string("doc/mail/approval_mail.txt",
                            dict(doc=doc,
                                 docs=[doc],
                                 doc_url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url(),
                                 to = addrs.to, 
                                 cc = addrs.cc,
                                 doc_type=doc_type,
                                 made_by=made_by,
                                 contacts=contacts,
                                 action_type=action_type,
                                 )
                            )

def generate_approval_mail_rfc_editor(request, doc):
    # This is essentially dead code - it is only exercised if the IESG ballots on some other stream's document,
    # which does not happen now that we have conflict reviews.
    disapproved = doc.get_state_slug("draft-iesg") in DO_NOT_PUBLISH_IESG_STATES
    doc_type = "RFC" if doc.get_state_slug() == "rfc" else "Internet Draft"
    addrs = gather_address_lists('ballot_approved_conflrev', doc=doc).as_strings()

    return render_to_string("doc/mail/approval_mail_rfc_editor.txt",
                            dict(doc=doc,
                                 doc_url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url(),
                                 doc_type=doc_type,
                                 disapproved=disapproved,
                                 to = addrs.to,
                                 cc = addrs.cc,
                                 )
                            )

def generate_publication_request(request, doc):
    group_description = ""
    if doc.group and doc.group.acronym != "none":
        group_description = doc.group.name_with_acronym()

    e = doc.latest_event(ConsensusDocEvent, type="changed_consensus")
    consensus = e.consensus if e else None

    if doc.stream_id == "irtf":
        approving_body = "IRSG"
        consensus_body = doc.group.acronym.upper()
    else:
        approving_body = str(doc.stream)
        consensus_body = approving_body

    return render_to_string("doc/mail/publication_request.txt",
                            dict(doc=doc,
                                 doc_url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url(),
                                 group_description=group_description,
                                 approving_body=approving_body,
                                 consensus_body=consensus_body,
                                 consensus=consensus,
                                 )
                            )

def send_last_call_request(request, doc):
    (to, cc) = gather_address_lists('last_call_requested',doc=doc)
    frm = '"DraftTracker Mail System" <iesg-secretary@ietf.org>'
    
    send_mail(request, to, frm,
              "Last Call: %s" % doc.file_tag(),
              "doc/mail/last_call_request.txt",
              dict(docs=[doc],
                   doc_url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url(),
                  ),
              cc=cc)

def email_resurrect_requested(request, doc, by):
    (to, cc) = gather_address_lists('resurrection_requested',doc=doc)

    if by.role_set.filter(name="secr", group__acronym="secretariat"):
        e = by.role_email("secr", group="secretariat")
    else:
        e = by.role_email("ad")
    frm = e.address

    send_mail(request, to, e.formatted_email(),
              "I-D Resurrection Request",
              "doc/mail/resurrect_request_email.txt",
              dict(doc=doc,
                   by=frm,
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url()),
              cc=cc)

def email_resurrection_completed(request, doc, requester):
    (to, cc) = gather_address_lists('resurrection_completed',doc=doc)
    frm = "I-D Administrator <internet-drafts-reply@ietf.org>"
    send_mail(request, to, frm,
              "I-D Resurrection Completed - %s" % doc.file_tag(),
              "doc/mail/resurrect_completed_email.txt",
              dict(doc=doc,
                   by=frm,
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url()),
              cc=cc)

def email_ballot_deferred(request, doc, by, telechat_date):
    (to, cc) = gather_address_lists('ballot_deferred',doc=doc)
    frm = "DraftTracker Mail System <iesg-secretary@ietf.org>"
    send_mail(request, to, frm,
              "IESG Deferred Ballot notification: %s" % doc.file_tag(),
              "doc/mail/ballot_deferred_email.txt",
              dict(doc=doc,
                   by=by,
                   action='deferred',
                   telechat_date=telechat_date),
              cc=cc)

def email_ballot_undeferred(request, doc, by, telechat_date):
    (to, cc)  = gather_address_lists('ballot_deferred',doc=doc)
    frm = "DraftTracker Mail System <iesg-secretary@ietf.org>"
    send_mail(request, to, frm,
              "IESG Undeferred Ballot notification: %s" % doc.file_tag(),
              "doc/mail/ballot_deferred_email.txt",
              dict(doc=doc,
                   by=by,
                   action='undeferred',
                   telechat_date=telechat_date),
              cc=cc)

def generate_issue_ballot_mail(request, doc, ballot):
    
    e = doc.latest_event(LastCallDocEvent, type="sent_last_call")
    last_call_expires = e.expires if e else None

    return render_to_string("doc/mail/issue_ballot_mail.txt",
                            dict(doc=doc,
                                 doc_url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url(),
                                 last_call_expires=last_call_expires,
                                 needed_ballot_positions=
                                   needed_ballot_positions(doc,
                                     doc.active_ballot().active_ad_positions().values()
                                   ),
                                 )
                            )

def email_iana(request, doc, to, msg, cc=None):
    # fix up message and send it with extra info on doc in headers
    import email
    parsed_msg = email.message_from_string(msg.encode("utf-8"))

    extra = {}
    extra["Reply-To"] = "noreply@ietf.org"
    extra["X-IETF-Draft-string"] = doc.name
    extra["X-IETF-Draft-revision"] = doc.rev
    
    send_mail_text(request, to,
                   parsed_msg["From"], parsed_msg["Subject"],
                   parsed_msg.get_payload(),
                   extra=extra,
                   cc=cc)

def extra_automation_headers(doc):
    extra = {}
    extra["X-IETF-Draft-string"] = doc.name
    extra["X-IETF-Draft-revision"] = doc.rev

    return extra

def email_last_call_expired(doc):
    text = "IETF Last Call has ended, and the state has been changed to\n%s." % doc.get_state("draft-iesg").name
    addrs = gather_address_lists('last_call_expired',doc=doc)
    
    send_mail(None,
              addrs.to,
              "DraftTracker Mail System <iesg-secretary@ietf.org>",
              "Last Call Expired: %s" % doc.file_tag(),
              "doc/mail/change_notice.txt",
              dict(text=text,
                   doc=doc,
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url()),
              cc = addrs.cc)

def email_intended_status_changed(request, doc, text):
    (to,cc) = gather_address_lists('doc_intended_status_changed',doc=doc)

    if not to:
        return
    
    text = strip_tags(text)
    send_mail(request, to, None,
              "Intended Status for %s changed to %s" % (doc.file_tag(),doc.intended_std_level),
              "doc/mail/intended_status_changed_email.txt",
              dict(text=text,
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url()),
              cc=cc)

def email_comment(request, doc, comment):
    (to, cc) = gather_address_lists('doc_added_comment',doc=doc)

    send_mail(request, to, None, "Comment added to %s history"%doc.name,
              "doc/mail/comment_added_email.txt",
              dict(
                comment=comment,
                doc=doc,
                by=request.user.person,
                url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url(),
              ),
              cc = cc)


def email_adopted(request, doc, prev_state, new_state, by, comment=""):
    (to, cc) = gather_address_lists('doc_adopted_by_group',doc=doc)

    state_type = (prev_state or new_state).type

    send_mail(request, to, settings.DEFAULT_FROM_EMAIL,
              u"The %s %s has adopted %s" % 
                  (doc.group.acronym.upper(),doc.group.type_id.upper(), doc.name),
              'doc/mail/doc_adopted_email.txt',
              dict(doc=doc,
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url(),
                   state_type=state_type,
                   prev_state=prev_state,
                   new_state=new_state,
                   by=by,
                   comment=comment),
              cc=cc)

def email_stream_state_changed(request, doc, prev_state, new_state, by, comment=""):
    (to, cc)= gather_address_lists('doc_stream_state_edited',doc=doc)

    state_type = (prev_state or new_state).type

    send_mail(request, to, settings.DEFAULT_FROM_EMAIL,
              u"%s changed for %s" % (state_type.label, doc.name),
              'doc/mail/stream_state_changed_email.txt',
              dict(doc=doc,
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url(),
                   state_type=state_type,
                   prev_state=prev_state,
                   new_state=new_state,
                   by=by,
                   comment=comment),
              cc=cc)

def email_stream_tags_changed(request, doc, added_tags, removed_tags, by, comment=""):

    (to, cc) = gather_address_lists('doc_stream_state_edited',doc=doc)

    send_mail(request, to, settings.DEFAULT_FROM_EMAIL,
              u"Tags changed for %s" % doc.name,
              'doc/mail/stream_tags_changed_email.txt',
              dict(doc=doc,
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url(),
                   added=added_tags,
                   removed=removed_tags,
                   by=by,
                   comment=comment),
              cc=cc)

def send_review_possibly_replaces_request(request, doc):
    addrs = gather_address_lists('doc_replacement_suggested',doc=doc)
    to = set(addrs.to)
    cc = set(addrs.cc)

    possibly_replaces = Document.objects.filter(name__in=[alias.name for alias in doc.related_that_doc("possibly-replaces")])
    for other_doc in possibly_replaces:
        (other_to, other_cc) = gather_address_lists('doc_replacement_suggested',doc=other_doc)
        to.update(other_to)
        cc.update(other_cc)

    send_mail(request, list(to), settings.DEFAULT_FROM_EMAIL,
              'Review of suggested possible replacements for %s-%s needed' % (doc.name, doc.rev),
              'doc/mail/review_possibly_replaces_request.txt', 
              dict(doc= doc,
                   possibly_replaces=doc.related_that_doc("possibly-replaces"),
                   review_url=settings.IDTRACKER_BASE_URL + urlreverse("doc_review_possibly_replaces", kwargs={ "name": doc.name })),
              cc=list(cc),)

def email_charter_internal_review(request, charter):
    addrs = gather_address_lists('charter_internal_review',doc=charter,group=charter.group)
    filename = '%s-%s.txt' % (charter.canonical_name(),charter.rev)
    charter_text = get_document_content(
                        filename,
                        os.path.join(settings.CHARTER_PATH,filename),
                        split=False,
                        markup=False,
                   )
    send_mail(request, addrs.to, settings.DEFAULT_FROM_EMAIL,
              'Internal WG Review: %s (%s)'%(charter.group.name,charter.group.acronym),
              'doc/mail/charter_internal_review.txt',
              dict(charter=charter,
                   chairs=charter.group.role_set.filter(name='chair').values_list('person__name',flat=True),
                   ads=charter.group.role_set.filter(name='ad').values_list('person__name',flat=True),
                   charter_text=charter_text,
                   milestones=charter.group.groupmilestone_set.filter(state="charter"),
                   review_type = "new" if charter.group.state_id == "proposed" else "recharter",
              ),
              cc=addrs.cc,
              extra={'Reply-To':"iesg@ietf.org"},
             )
