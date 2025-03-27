# Copyright The IETF Trust 2010-2020, All Rights Reserved
# -*- coding: utf-8 -*-
# generation of mails 


import datetime
import textwrap

from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.urls import reverse as urlreverse
from django.utils import timezone
from django.utils.encoding import force_str

import debug                            # pyflakes:ignore
from ietf.doc.templatetags.mail_filters import std_level_prompt

from ietf.utils import log
from ietf.utils.mail import send_mail, send_mail_text
from ietf.ipr.utils import iprs_from_docs, related_docs
from ietf.doc.models import WriteupDocEvent, LastCallDocEvent, ConsensusDocEvent
from ietf.doc.utils import needed_ballot_positions
from ietf.doc.utils_bofreq import bofreq_editors, bofreq_responsible
from ietf.group.models import Role
from ietf.doc.models import Document
from ietf.mailtrigger.utils import gather_address_lists
from ietf.utils.timezone import date_today, DEADLINE_TZINFO


def email_state_changed(request, doc, text, mailtrigger_id=None):
    (to,cc) = gather_address_lists(mailtrigger_id or 'doc_state_edited',doc=doc)
    if not to:
        return
    
    text = strip_tags(text)
    send_mail(request, to, None,
              "Datatracker State Update Notice: %s" % doc.file_tag(),
              "doc/mail/state_changed_email.txt",
              dict(text=text,
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url()),
              cc=cc)
    
def email_ad_approved_doc(request, doc, text):
        to = "iesg@iesg.org"
        bcc = "iesg-secretary@ietf.org"
        frm = request.user.person.formatted_email()
        send_mail(request, to, frm,
                          "Approved: %s" % doc.filename_with_rev(),
                          "doc/mail/ad_approval_email.txt",
                          dict(text=text,
                                   docname=doc.filename_with_rev()),
                          bcc=bcc)

def email_ad_approved_conflict_review(request, review, ok_to_publish):
    """Email notification when AD approves a conflict review"""
    conflictdoc = review.relateddocument_set.get(relationship__slug='conflrev').target
    (to, cc) = gather_address_lists("ad_approved_conflict_review")
    frm = request.user.person.formatted_email()
    send_mail(request,
              to,
              frm,
              "Approved: %s" % review.title,
              "doc/conflict_review/ad_approval_pending_email.txt",
              dict(ok_to_publish=ok_to_publish,
                   review=review,
                   conflictdoc=conflictdoc),
              cc=cc)

def email_ad_approved_status_change(request, status_change, related_doc_info):
    """Email notification when AD approves a status change"""
    (to, cc) = gather_address_lists("ad_approved_status_change")
    frm = request.user.person.formatted_email()
    send_mail(request,
              to,
              frm,
              "Approved: %s" % status_change.title,
              "doc/status_change/ad_approval_pending_email.txt",
              dict(
                  related_doc_info=related_doc_info
              ),
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
        text = "Stream changed to <b>%s</b> from %s" % (new_stream, old_stream)
    text = strip_tags(text)

    send_mail(request, to, None,
              "I-D Tracker Stream Change Notice: %s" % doc.file_tag(),
              "doc/mail/stream_changed_email.txt",
              dict(text=text,
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url()),
              cc=cc)

def email_pulled_from_rfc_queue(request, doc, comment, prev_state, next_state):
    extra=extra_automation_headers(doc)
    addrs = gather_address_lists('doc_pulled_from_rfc_queue',doc=doc)
    extra['Cc'] = addrs.cc
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
    tagless_changes = []
    for c in changes:
        tagless_changes.append(strip_tags(c))
    send_mail(request, addrs.to, None,
              'IESG processing details changed for %s' % doc.name,
              'doc/mail/email_iesg_processing.txt', 
              dict(doc=doc,
                   changes=tagless_changes,
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url()),
              cc=addrs.cc)

def email_remind_action_holders(request, doc, note=None):
    addrs = gather_address_lists('doc_remind_action_holders', doc=doc)
    log.assertion(
        'not doc.action_holders.exclude(email__in=addrs.to).exists()',
        note='All action holders should receive a reminder email. Failed for %s.' % doc.name,
    )
    send_mail(request, addrs.to, None,
              'Reminder: action needed for %s' % doc.display_name(),
              'doc/mail/remind_action_holders_mail.txt',
              dict(
                  doc=doc,
                  doc_url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url(),
                  note=note,
              ),
              cc=addrs.cc)

def html_to_text(html):
    return strip_tags(html.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").replace("<br>", "\n"))
    
def email_update_telechat(request, doc, text):
    (to, cc) = gather_address_lists('doc_telechat_details_changed',doc=doc)

    if not to:
        return
    
    text = strip_tags(text)
    send_mail(request, to, None,
              "Telechat update notice: %s" % doc.file_tag(),
              "doc/mail/update_telechat.txt",
              dict(text=text,
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url()),
              cc=cc)


def generate_ballot_writeup(request, doc):
    e = doc.latest_event(type="iana_review")
    iana = e.desc if e else ""

    e = WriteupDocEvent()
    e.type = "changed_ballot_writeup_text"
    e.by = request.user.person
    e.doc = doc
    e.rev = doc.rev
    e.desc = "Ballot writeup was generated"
    e.text = force_str(render_to_string("doc/mail/ballot_writeup.txt", {'iana': iana, 'doc': doc }))

    # caller is responsible for saving, if necessary
    return e
    
def generate_ballot_rfceditornote(request, doc):
    e = WriteupDocEvent()
    e.type = "changed_ballot_rfceditornote_text"
    e.by = request.user.person
    e.doc = doc
    e.rev = doc.rev
    e.desc = "RFC Editor Note for ballot was generated"
    e.text = force_str(render_to_string("doc/mail/ballot_rfceditornote.txt"))
    e.save()
    
    return e

def generate_last_call_announcement(request, doc):
    expiration_date = date_today(DEADLINE_TZINFO) + datetime.timedelta(days=14)
    if doc.group.type_id in ("individ", "area"):
        group = "an individual submitter"
        expiration_date += datetime.timedelta(days=14)
    else:
        group = "the %s %s (%s)" % (doc.group.name, doc.group.type.name, doc.group.acronym)

    doc.filled_title = textwrap.fill(doc.title, width=70, subsequent_indent=" " * 3)
    
    iprs = iprs_from_docs(related_docs(Document.objects.get(name=doc.name)))
    if iprs:
        ipr_links = [ urlreverse("ietf.ipr.views.show", kwargs=dict(id=i.id)) for i in iprs]
        ipr_links = [ settings.IDTRACKER_BASE_URL+url if not url.startswith("http") else url for url in ipr_links ]
    else:
        ipr_links = None

    downrefs = [rel for rel in doc.relateddocument_set.all() if rel.is_downref() and not rel.is_approved_downref()]

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
                                 downrefs=downrefs,
                                 )
                            )

    e = WriteupDocEvent()
    e.type = "changed_last_call_text"
    e.by = request.user.person
    e.doc = doc
    e.rev = doc.rev
    e.desc = "Last call announcement was generated"
    e.text = force_str(mail)

    # caller is responsible for saving, if necessary
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
    e.rev = doc.rev
    e.desc = "Ballot approval text was generated"
    e.text = force_str(mail)

    # caller is responsible for saving, if necessary
    return e

def generate_approval_mail_approved(request, doc):

    if doc.intended_std_level_id in ("std", "ds", "ps", "bcp"):
        action_type = "Protocol"
    else:
        action_type = "Document"

    # the second check catches some area working groups (like
    # Transport Area Working Group)
    if doc.group.type_id not in ("area", "individ", "ag", "rg", "rag") and not doc.group.name.endswith("Working Group"):
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

    doc_type = "RFC" if doc.get_state_slug() == "rfc" else "Internet-Draft"
        
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
    doc_type = "RFC" if doc.get_state_slug() == "rfc" else "Internet-Draft"
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
        group_description = doc.group.name
        if doc.group.type_id not in ("ietf", "irtf", "iab",):
            group_description += " %s (%s)" % (doc.group.type, doc.group.acronym)

    e = doc.latest_event(ConsensusDocEvent, type="changed_consensus")
    consensus = e.consensus if e else None

    if doc.stream_id == "irtf":
        approving_body = "IRSG"
        consensus_body = doc.group.acronym.upper()
    if doc.stream_id == "editorial":
        approving_body = "RSAB"
        consensus_body = doc.group.acronym.upper()
    else:
        approving_body = str(doc.stream)
        consensus_body = approving_body

    e = doc.latest_event(WriteupDocEvent, type="changed_rfc_editor_note_text")
    rfcednote = e.text if e else ""

    return render_to_string("doc/mail/publication_request.txt",
                            dict(doc=doc,
                                 doc_url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url(),
                                 group_description=group_description,
                                 approving_body=approving_body,
                                 consensus_body=consensus_body,
                                 consensus=consensus,
                                 rfc_editor_note=rfcednote,
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
    last_call_has_expired = last_call_expires and last_call_expires < timezone.now()

    return render_to_string("doc/mail/issue_iesg_ballot_mail.txt",
                            dict(doc=doc,
                                 doc_url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url(),
                                 last_call_expires=last_call_expires,
                                 last_call_has_expired=last_call_has_expired,
                                 needed_ballot_positions=
                                   needed_ballot_positions(doc,
                                     list(doc.active_ballot().active_balloter_positions().values())
                                   ),
                                 )
                            )

def _send_irsg_ballot_email(request, doc, ballot, subject, template):
    """Send email notification when IRSG ballot is issued"""
    (to, cc) = gather_address_lists('irsg_ballot_issued', doc=doc)
    sender = 'IESG Secretary <iesg-secretary@ietf.org>'

    ballot_expired = ballot.duedate < timezone.now()
    active_ballot = doc.active_ballot()
    if active_ballot is None:
        needed_bps = ''
    else:
        needed_bps = needed_ballot_positions(
            doc,
            list(active_ballot.active_balloter_positions().values())
        )

    return send_mail(
        request=request,
        frm=sender,
        to=to,
        cc=cc,
        subject=subject,
        extra={'Reply-To': [sender]},
        template=template,
        context=dict(
            doc=doc,
            doc_url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url(),
            ballot_duedate=ballot.duedate,
            ballot_expired=ballot_expired,
            needed_ballot_positions=needed_bps,
        ))


def email_irsg_ballot_issued(request, doc, ballot):
    """Send email notification when IRSG ballot is issued"""
    return _send_irsg_ballot_email(
        request,
        doc,
        ballot,
        'IRSG ballot issued: %s to %s'%(doc.file_tag(), std_level_prompt(doc)),
        'doc/mail/issue_irsg_ballot_mail.txt',
    )

def email_irsg_ballot_closed(request, doc, ballot):
    """Send email notification when IRSG ballot is closed"""
    return _send_irsg_ballot_email(
        request,
        doc,
        ballot,
        'IRSG ballot closed: %s to %s'%(doc.file_tag(), std_level_prompt(doc)),
        "doc/mail/close_irsg_ballot_mail.txt",
    )

def _send_rsab_ballot_email(request, doc, ballot, subject, template):
    """Send email notification when IRSG ballot is issued"""
    (to, cc) = gather_address_lists('rsab_ballot_issued', doc=doc)
    sender = 'IESG Secretary <iesg-secretary@ietf.org>'

    active_ballot = doc.active_ballot()
    if active_ballot is None:
        needed_bps = ''
    else:
        needed_bps = needed_ballot_positions(
            doc,
            list(active_ballot.active_balloter_positions().values())
        )

    return send_mail(
        request=request,
        frm=sender,
        to=to,
        cc=cc,
        subject=subject,
        extra={'Reply-To': [sender]},
        template=template,
        context=dict(
            doc=doc,
            doc_url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url(),
            needed_ballot_positions=needed_bps,
        ))

def email_rsab_ballot_issued(request, doc, ballot):
    """Send email notification when RSAB ballot is issued"""
    return _send_rsab_ballot_email(
        request,
        doc,
        ballot,
        'RSAB ballot issued: %s to %s'%(doc.file_tag(), std_level_prompt(doc)),
        'doc/mail/issue_rsab_ballot_mail.txt',
    )

def email_rsab_ballot_closed(request, doc, ballot):
    """Send email notification when RSAB ballot is closed"""
    return _send_rsab_ballot_email(
        request,
        doc,
        ballot,
        'RSAB ballot closed: %s to %s'%(doc.file_tag(), std_level_prompt(doc)),
        "doc/mail/close_rsab_ballot_mail.txt",
    )

def email_iana(request, doc, to, msg, cc=None):
    # fix up message and send it with extra info on doc in headers
    import email
    parsed_msg = email.message_from_string(msg)
    parsed_msg.set_charset('UTF-8')

    extra = extra_automation_headers(doc)
    extra["Reply-To"] = ["noreply@ietf.org", ]
    
    send_mail_text(request, to,
                   parsed_msg["From"], parsed_msg["Subject"],
                   parsed_msg.get_payload(),
                   extra=extra,
                   cc=cc)

def extra_automation_headers(doc):
    extra = {}
    extra["X-IETF-Draft-string"] = [ doc.name, ]
    extra["X-IETF-Draft-revision"] = [ doc.rev, ]

    return extra

def email_last_call_expired(doc):
    if not doc.type_id in ['draft','statchg']:
        return
    text = "IETF Last Call has ended, and the state has been changed to\n%s." % doc.get_state("draft-iesg" if doc.type_id == 'draft' else "statchg").name
    addrs = gather_address_lists('last_call_expired',doc=doc)
    
    send_mail(None,
              addrs.to,
              "DraftTracker Mail System <iesg-secretary@ietf.org>",
              "IETF Last Call Expired: %s" % doc.file_tag(),
              "doc/mail/change_notice.txt",
              dict(text=text,
                   doc=doc,
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url()),
              cc = addrs.cc)

def email_last_call_expired_with_downref(doc, last_call_text):
    if doc.type_id != 'draft':
        return
    send_mail(None,
              (doc.ad.email().address, ),
              "DraftTracker Mail System <iesg-secretary@ietf.org>",
              "Review Downrefs From Expired Last Call: %s" % doc.file_tag(),
              "doc/mail/downrefs_notice.txt",
              dict(last_call_text=last_call_text,
                   doc=doc,
                   url=settings.IDTRACKER_BASE_URL + "/downref/add/"))

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
              'The %s %s has placed %s in state "%s"' % 
                  (doc.group.acronym.upper(),doc.group.type_id.upper(), doc.name, new_state or "None"),
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
              "%s changed for %s" % (state_type.label, doc.name),
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
              "Tags changed for %s" % doc.name,
              'doc/mail/stream_tags_changed_email.txt',
              dict(doc=doc,
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url(),
                   added=added_tags,
                   removed=removed_tags,
                   by=by,
                   comment=comment),
              cc=cc)

def send_review_possibly_replaces_request(request, doc, submitter_info):
    addrs = gather_address_lists('doc_replacement_suggested',doc=doc)
    to = set(addrs.to)
    cc = set(addrs.cc)

    possibly_replaces = Document.objects.filter(name__in=[related.name for related in doc.related_that_doc("possibly-replaces")])
    for other_doc in possibly_replaces:
        (other_to, other_cc) = gather_address_lists('doc_replacement_suggested',doc=other_doc)
        to.update(other_to)
        cc.update(other_cc)

    send_mail(request, list(to), settings.DEFAULT_FROM_EMAIL,
              'Review of suggested possible replacements for %s-%s needed' % (doc.name, doc.rev),
              'doc/mail/review_possibly_replaces_request.txt', 
              dict(doc= doc,
                   submitter_info=submitter_info,
                   possibly_replaces=doc.related_that_doc("possibly-replaces"),
                   review_url=settings.IDTRACKER_BASE_URL + urlreverse('ietf.doc.views_draft.review_possibly_replaces', kwargs={ "name": doc.name })),
              cc=list(cc),)

def email_charter_internal_review(request, charter):
    addrs = gather_address_lists('charter_internal_review',doc=charter,group=charter.group)
    charter_text = charter.text_or_error()     # pyflakes:ignore

    send_mail(request, addrs.to, settings.DEFAULT_FROM_EMAIL,
              'Internal %s Review: %s (%s)'%(charter.group.type.name,charter.group.name,charter.group.acronym),
              'doc/mail/charter_internal_review.txt',
              dict(charter=charter,
                   charter_text=charter_text,
                   review_type = "new" if charter.group.state_id == "proposed" else "recharter",
                   charter_url=settings.IDTRACKER_BASE_URL + charter.get_absolute_url(),
                   chairs=charter.group.role_set.filter(name="chair"),
                   secr=charter.group.role_set.filter(name="secr"),
                   ads=charter.group.role_set.filter(name='ad'),
                   parent_ads=charter.group.parent.role_set.filter(name='ad'),
                   techadv=charter.group.role_set.filter(name="techadv"),
                   milestones=charter.group.groupmilestone_set.filter(state="charter"),
              ),
              cc=addrs.cc,
              extra={'Reply-To': ["irsg@irtf.org" if charter.group.type_id == 'rg' else "iesg@ietf.org", ]},
             )

def email_lc_to_yang_doctors(request, doc):
    addrs = gather_address_lists('last_call_of_doc_with_yang_issued')
    send_mail(request, addrs.to, settings.DEFAULT_FROM_EMAIL,
              'Attn YangDoctors: IETF LC issued for %s' % doc.name ,
              'doc/mail/lc_to_yang_doctors.txt',
              dict(doc=doc, url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url() ),
              cc = addrs.cc,
             )

def email_iana_expert_review_state_changed(request, events):
    assert type(events) == list
    assert len(events) == 1
    addrs = gather_address_lists('iana_expert_review_state_changed', doc=events[0].doc)
    send_mail(request, addrs.to, settings.DEFAULT_FROM_EMAIL,
              f'IANA expert review state changed to {events[0].state.name} for {events[0].doc.name}',
              'doc/mail/iana_expert_review_state_changed.txt',
              dict(event=events[0], url=settings.IDTRACKER_BASE_URL + events[0].doc.get_absolute_url() ),
              cc = addrs.cc,
             )

def send_external_resource_change_request(request, doc, submitter_info, requested_resources):
    """Send an email to requesting changes to a draft's external resources"""
    addrs = gather_address_lists('doc_external_resource_change_requested', doc=doc)
    to = set(addrs.to)
    cc = set(addrs.cc)

    send_mail(request, list(to), settings.DEFAULT_FROM_EMAIL,
              'External resource change requested for %s' % doc.name,
              'doc/mail/external_resource_change_request.txt',
              dict(
                  doc=doc,
                  submitter_info=submitter_info,
                  requested_resources=requested_resources,
                  doc_url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url(),
              ),
              cc=list(cc),)

def email_bofreq_title_changed(request, bofreq):
    addrs = gather_address_lists('bofreq_title_changed', doc=bofreq)

    send_mail(request, addrs.to, settings.DEFAULT_FROM_EMAIL,
              f'BOF Request title changed : {bofreq.name}',
              'doc/mail/bofreq_title_changed.txt',
              dict(bofreq=bofreq, request=request),
              cc=addrs.cc)

def plain_names(persons):
    return [p.plain_name() for p in persons]

def email_bofreq_editors_changed(request, bofreq, previous_editors):
    editors = bofreq_editors(bofreq)
    addrs = gather_address_lists('bofreq_editors_changed', doc=bofreq, previous_editors=previous_editors)

    send_mail(request, addrs.to, settings.DEFAULT_FROM_EMAIL,
              f'BOF Request editors changed : {bofreq.name}',
              'doc/mail/bofreq_editors_changed.txt',
              dict(bofreq=bofreq, request=request, editors=plain_names(editors), previous_editors=plain_names(previous_editors)),
              cc=addrs.cc)

def email_bofreq_responsible_changed(request, bofreq, previous_responsible):
    responsible = bofreq_responsible(bofreq)
    addrs = gather_address_lists('bofreq_responsible_changed', doc=bofreq, previous_responsible=previous_responsible)

    send_mail(request, addrs.to, settings.DEFAULT_FROM_EMAIL,
              f'BOF Request responsible leadership changed : {bofreq.name}',
              'doc/mail/bofreq_responsible_changed.txt',
              dict(bofreq=bofreq, request=request, responsible=plain_names(responsible), previous_responsible=plain_names(previous_responsible)),
              cc=addrs.cc)

def email_bofreq_new_revision(request, bofreq):
    addrs = gather_address_lists('bofreq_new_revision', doc=bofreq)
    send_mail(request, addrs.to, settings.DEFAULT_FROM_EMAIL,
              f'New BOF request revision uploaded: {bofreq.name}-{bofreq.rev}',
              'doc/mail/bofreq_new_revision.txt',
              dict(bofreq=bofreq, request=request ),
              cc=addrs.cc)
