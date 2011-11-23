# generation of mails 

import textwrap
from datetime import datetime, date, time, timedelta

from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.core.urlresolvers import reverse as urlreverse

from ietf.utils.mail import send_mail, send_mail_text
from ietf.idtracker.models import *
from ietf.ipr.search import iprs_from_docs
from ietf.ietfworkflows.streams import (get_stream_from_draft)
from ietf.ietfworkflows.models import (Stream)
from redesign.doc.models import WriteupDocEvent, BallotPositionDocEvent, LastCallDocEvent, DocAlias
from redesign.person.models import Person

def email_state_changed(request, doc, text):
    to = [x.strip() for x in doc.idinternal.state_change_notice_to.replace(';', ',').split(',')]
    if to:
        send_mail(request, to, None,
              "ID Tracker State Update Notice: %s" % doc.file_tag(),
              "idrfc/state_changed_email.txt",
              dict(text=text,
                   url=settings.IDTRACKER_BASE_URL + doc.idinternal.get_absolute_url()))

def email_state_changedREDESIGN(request, doc, text):
    to = [x.strip() for x in doc.notify.replace(';', ',').split(',')]
    if not to:
        return
    
    text = strip_tags(text)
    send_mail(request, to, None,
              "ID Tracker State Update Notice: %s" % doc.file_tag(),
              "idrfc/state_changed_email.txt",
              dict(text=text,
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url()))

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    email_state_changed = email_state_changedREDESIGN
    
def html_to_text(html):
    return strip_tags(html.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").replace("<br>", "\n"))
    
def email_owner(request, doc, owner, changed_by, text, subject=None):
    if not owner or not changed_by or owner == changed_by:
        return

    to = u"%s <%s>" % owner.person.email()
    send_mail(request, to,
              "DraftTracker Mail System <iesg-secretary@ietf.org>",
              "%s updated by %s" % (doc.file_tag(), changed_by),
              "idrfc/change_notice.txt",
              dict(text=html_to_text(text),
                   doc=doc,
                   url=settings.IDTRACKER_BASE_URL + doc.idinternal.get_absolute_url()))

def email_ownerREDESIGN(request, doc, owner, changed_by, text, subject=None):
    if not owner or not changed_by or owner == changed_by:
        return

    to = owner.formatted_email()
    send_mail(request, to,
              "DraftTracker Mail System <iesg-secretary@ietf.org>",
              "%s updated by %s" % (doc.file_tag(), changed_by.name),
              "idrfc/change_notice.txt",
              dict(text=html_to_text(text),
                   doc=doc,
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url()))

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    email_owner = email_ownerREDESIGN


def full_intended_status(intended_status):
    s = str(intended_status)
    # FIXME: this should perhaps be defined in the db
    if "Informational" in s:
        return "an Informational RFC"
    elif "Experimental" in s:
        return "an Experimental RFC"
    elif "Proposed" in s:
        return "a Proposed Standard"
    elif "Draft" in s:
        return "a Draft Standard"
    elif "BCP" in s:
        return "a BCP"
    elif "Standard" in s:
        return "a Full Standard"
    elif "Request" in s or "None" in s:
        return "*** YOU MUST SELECT AN INTENDED STATUS FOR THIS DRAFT AND REGENERATE THIS TEXT ***"
    else:
        return "a %s" % s
    
def generate_ballot_writeup(request, doc):
    e = WriteupDocEvent()
    e.type = "changed_ballot_writeup_text"
    e.by = request.user.get_profile()
    e.doc = doc
    e.desc = u"Ballot writeup was generated"
    e.text = unicode(render_to_string("idrfc/ballot_writeup.txt"))
    e.save()
    
    return e
    
def generate_last_call_announcement(request, doc):
    status = full_intended_status(doc.intended_status).replace("a ", "").replace("an ", "")
    
    expiration_date = date.today() + timedelta(days=14)
    cc = []
    if doc.group.acronym_id == Acronym.INDIVIDUAL_SUBMITTER:
        group = "an individual submitter"
        expiration_date += timedelta(days=14)
    else:
        group = "the %s WG (%s)" % (doc.group.name, doc.group.acronym)
        cc.append(doc.group.ietfwg.email_address)

    urls = []
    docs = [d.document() for d in doc.idinternal.ballot_set()]
    for d in docs:
        d.full_status = full_intended_status(d.intended_status)
        d.filled_title = textwrap.fill(d.title, width=70, subsequent_indent=" " * 3)
        urls.append(settings.IDTRACKER_BASE_URL + d.idinternal.get_absolute_url())
    
    iprs, docs = iprs_from_docs(docs)
    if iprs:
        ipr_links = [ urlreverse("ietf.ipr.views.show", kwargs=dict(ipr_id=i.ipr_id)) for i in iprs]
        ipr_links = [ settings.IDTRACKER_BASE_URL+url if not url.startswith("http") else url for url in ipr_links ]
    else:
        ipr_links = None

    return render_to_string("idrfc/last_call_announcement.txt",
                            dict(doc=doc,
                                 doc_url=settings.IDTRACKER_BASE_URL + doc.idinternal.get_absolute_url(),
                                 expiration_date=expiration_date.strftime("%Y-%m-%d"), #.strftime("%B %-d, %Y"),
                                 cc=", ".join("<%s>" % e for e in cc),
                                 group=group,
                                 docs=docs,
                                 urls=urls,
                                 status=status,
                                 impl_report="Draft" in status or "Full" in status,
                                 ipr_links=ipr_links,
                                 )
                            )

def generate_last_call_announcementREDESIGN(request, doc):
    doc.full_status = full_intended_status(doc.intended_std_level)
    status = doc.full_status.replace("a ", "").replace("an ", "")
    
    expiration_date = date.today() + timedelta(days=14)
    cc = []
    if doc.group.type_id == "individ":
        group = "an individual submitter"
        expiration_date += timedelta(days=14)
    else:
        group = "the %s WG (%s)" % (doc.group.name, doc.group.acronym)
        if doc.group.list_email:
            cc.append(doc.group.list_email)

    doc.filled_title = textwrap.fill(doc.title, width=70, subsequent_indent=" " * 3)
    
    iprs, _ = iprs_from_docs([ DocAlias.objects.get(name=doc.canonical_name()) ])
    if iprs:
        ipr_links = [ urlreverse("ietf.ipr.views.show", kwargs=dict(ipr_id=i.ipr_id)) for i in iprs]
        ipr_links = [ settings.IDTRACKER_BASE_URL+url if not url.startswith("http") else url for url in ipr_links ]
    else:
        ipr_links = None

    mail = render_to_string("idrfc/last_call_announcement.txt",
                            dict(doc=doc,
                                 doc_url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url() + "ballot/",
                                 expiration_date=expiration_date.strftime("%Y-%m-%d"), #.strftime("%B %-d, %Y"),
                                 cc=", ".join("<%s>" % e for e in cc),
                                 group=group,
                                 docs=[ doc ],
                                 urls=[ settings.IDTRACKER_BASE_URL + doc.get_absolute_url() ],
                                 status=status,
                                 impl_report="Draft" in status or "Full" in status,
                                 ipr_links=ipr_links,
                                 )
                            )

    e = WriteupDocEvent()
    e.type = "changed_last_call_text"
    e.by = request.user.get_profile()
    e.doc = doc
    e.desc = u"Last call announcement was generated"
    e.text = unicode(mail)
    e.save()

    return e
    

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    generate_last_call_announcement = generate_last_call_announcementREDESIGN

def generate_approval_mail(request, doc):
    if doc.idinternal.cur_state_id in IDState.DO_NOT_PUBLISH_STATES or doc.idinternal.via_rfc_editor:
        return generate_approval_mail_rfc_editor(request, doc)
    
    status = full_intended_status(doc.intended_status).replace("a ", "").replace("an ", "")
    if "an " in full_intended_status(doc.intended_status):
        action_type = "Document"
    else:
        action_type = "Protocol"
    
    cc = settings.DOC_APPROVAL_EMAIL_CC

    if doc.group.ietfwg.group_type.type != "AG" and not doc.group.name.endswith("Working Group"):
        doc.group.name_with_wg = doc.group.name + " Working Group"
        cc.append("%s mailing list <%s>" % (doc.group.acronym, doc.group.ietfwg.email_address))
        cc.append("%s chair <%s-chairs@tools.ietf.org>" % (doc.group.acronym, doc.group.acronym))
    else:
        doc.group.name_with_wg = doc.group.name

    docs = [d.document() for d in doc.idinternal.ballot_set()]
    for d in docs:
        d.full_status = full_intended_status(d.intended_status)
        d.filled_title = textwrap.fill(d.title, width=70, subsequent_indent=" " * 3)

    if doc.group.acronym_id == Acronym.INDIVIDUAL_SUBMITTER:
        if len(docs) > 1:
            made_by = "These documents have been reviewed in the IETF but are not the products of an IETF Working Group."
        else:
            made_by = "This document has been reviewed in the IETF but is not the product of an IETF Working Group."
    else:
        if len(docs) > 1:
            made_by = "These documents are products of the %s." % doc.group.name_with_wg
        else:
            made_by = "This document is the product of the %s." % doc.group.name_with_wg
    
    director = doc.idinternal.job_owner
    other_director = IESGLogin.objects.filter(person__in=[ad.person for ad in doc.group.ietfwg.area_directors()]).exclude(id=doc.idinternal.job_owner_id)
    if doc.group.acronym_id != Acronym.INDIVIDUAL_SUBMITTER and other_director:
        contacts = "The IESG contact persons are %s and %s." % (director, other_director[0])
    else:
        contacts = "The IESG contact person is %s." % director

    doc_type = "RFC" if type(doc) == Rfc else "Internet Draft"
        
    return render_to_string("idrfc/approval_mail.txt",
                            dict(doc=doc,
                                 doc_url=settings.IDTRACKER_BASE_URL + doc.idinternal.get_absolute_url(),
                                 cc=",\n    ".join(cc),
                                 docs=docs,
                                 doc_type=doc_type,
                                 made_by=made_by,
                                 contacts=contacts,
                                 status=status,
                                 action_type=action_type,
                                 )
                            )

def generate_approval_mail_rfc_editor(request, doc):
    full_status = full_intended_status(doc.intended_status)
    status = full_status.replace("a ", "").replace("an ", "")
    disapproved = doc.idinternal.cur_state_id in IDState.DO_NOT_PUBLISH_STATES
    doc_type = "RFC" if type(doc) == Rfc else "Internet Draft"
    
    stream = get_stream_from_draft(doc)
    to = ", ".join([u"%s <%s>" % x.email() for x in stream.get_chairs_for_document(doc) ])
    if stream.name == "IRTF":
    	# also send to the IRSG
        to += ", Internet Research Steering Group (IRSG) <irsg@irtf.org>"

    return render_to_string("idrfc/approval_mail_rfc_editor.txt",
                            dict(doc=doc,
                                 doc_url=settings.IDTRACKER_BASE_URL + doc.idinternal.get_absolute_url(),
                                 doc_type=doc_type,
                                 status=status,
                                 full_status=full_status,
                                 disapproved=disapproved,
                                 to=to,
                                 )
                            )

DO_NOT_PUBLISH_IESG_STATES = ("nopubadw", "nopubanw")

def generate_approval_mailREDESIGN(request, doc):
    if doc.get_state_slug("draft-iesg") in DO_NOT_PUBLISH_IESG_STATES or doc.tags.filter(slug='via-rfc'):
        mail = generate_approval_mail_rfc_editor(request, doc)
    else:
        mail = generate_approval_mail_approved(request, doc)

    e = WriteupDocEvent()
    e.type = "changed_ballot_approval_text"
    e.by = request.user.get_profile()
    e.doc = doc
    e.desc = u"Ballot approval text was generated"
    e.text = unicode(mail)
    e.save()

    return e

def generate_approval_mail_approved(request, doc):
    doc.full_status = full_intended_status(doc.intended_std_level.name)
    status = doc.full_status.replace("a ", "").replace("an ", "")
    
    if "an " in status:
        action_type = "Document"
    else:
        action_type = "Protocol"
    
    cc = settings.DOC_APPROVAL_EMAIL_CC

    # the second check catches some area working groups (like
    # Transport Area Working Group)
    if doc.group.type_id != "area" and not doc.group.name.endswith("Working Group"):
        doc.group.name_with_wg = doc.group.name + " Working Group"
        if doc.group.list_email:
            cc.append("%s mailing list <%s>" % (doc.group.acronym, doc.group.list_email))
        cc.append("%s chair <%s-chairs@tools.ietf.org>" % (doc.group.acronym, doc.group.acronym))
    else:
        doc.group.name_with_wg = doc.group.name

    doc.filled_title = textwrap.fill(doc.title, width=70, subsequent_indent=" " * 3)

    if doc.group.type_id == "individ":
        made_by = "This document has been reviewed in the IETF but is not the product of an IETF Working Group."
    else:
        made_by = "This document is the product of the %s." % doc.group.name_with_wg
    
    director = doc.ad
    other_director = Person.objects.filter(role__group__role__person=director, role__group__role__name="ad").exclude(pk=director.pk)
    
    if doc.group.type_id != "individ" and other_director:
        contacts = "The IESG contact persons are %s and %s." % (director.name, other_director[0].name)
    else:
        contacts = "The IESG contact person is %s." % director.name

    doc_type = "RFC" if doc.get_state_slug() == "rfc" else "Internet Draft"
        
    return render_to_string("idrfc/approval_mail.txt",
                            dict(doc=doc,
                                 docs=[doc],
                                 doc_url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url(),
                                 cc=",\n    ".join(cc),
                                 doc_type=doc_type,
                                 made_by=made_by,
                                 contacts=contacts,
                                 status=status,
                                 action_type=action_type,
                                 )
                            )

def generate_approval_mail_rfc_editorREDESIGN(request, doc):
    full_status = full_intended_status(doc.intended_std_level.name)
    status = full_status.replace("a ", "").replace("an ", "")
    disapproved = doc.get_state_slug("draft-iesg") in DO_NOT_PUBLISH_IESG_STATES
    doc_type = "RFC" if doc.get_state_slug() == "rfc" else "Internet Draft"

    to = []
    if doc.group:
        for r in doc.group.role_set.filter(name="chair").select_related():
            to.append(r.formatted_email())

        if doc.stream_id == "ise":
            # include ISE chair
            g = Group.objects.get(type='individ')
            for r in g.role_set.filter(name="chair").select_related():
                to.append(r.formatted_email())
        elif doc.stream_id == "irtf":
            # include IRTF chair
            g = Group.objects.get(type='irtf')
            for r in g.role_set.filter(name="chair").select_related():
                to.append(r.formatted_email())
            # and IRSG
            to.append('"Internet Research Steering Group" <irsg@irtf.org>')

    return render_to_string("idrfc/approval_mail_rfc_editor.txt",
                            dict(doc=doc,
                                 doc_url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url(),
                                 doc_type=doc_type,
                                 status=status,
                                 full_status=full_status,
                                 disapproved=disapproved,
                                 to=", ".join(to),
                                 )
                            )

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    generate_approval_mail = generate_approval_mailREDESIGN
    generate_approval_mail_rfc_editor = generate_approval_mail_rfc_editorREDESIGN


def send_last_call_request(request, doc, ballot):
    to = "iesg-secretary@ietf.org"
    frm = '"DraftTracker Mail System" <iesg-secretary@ietf.org>'
    docs = [d.document() for d in doc.idinternal.ballot_set()]
    
    send_mail(request, to, frm,
              "Last Call: %s" % doc.file_tag(),
              "idrfc/last_call_request.txt",
              dict(docs=docs,
                   doc_url=settings.IDTRACKER_BASE_URL + doc.idinternal.get_absolute_url()))

def send_last_call_requestREDESIGN(request, doc):
    to = "iesg-secretary@ietf.org"
    frm = '"DraftTracker Mail System" <iesg-secretary@ietf.org>'
    
    send_mail(request, to, frm,
              "Last Call: %s" % doc.file_tag(),
              "idrfc/last_call_request.txt",
              dict(docs=[doc],
                   doc_url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url()))

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    send_last_call_request = send_last_call_requestREDESIGN

def email_resurrect_requested(request, doc, by):
    to = "I-D Administrator <internet-drafts@ietf.org>"
    frm = u"%s <%s>" % by.person.email()
    send_mail(request, to, frm,
              "I-D Resurrection Request",
              "idrfc/resurrect_request_email.txt",
              dict(doc=doc,
                   by=frm,
                   url=settings.IDTRACKER_BASE_URL + doc.idinternal.get_absolute_url()))

def email_resurrect_requestedREDESIGN(request, doc, by):
    to = "I-D Administrator <internet-drafts@ietf.org>"
    frm = by.formatted_email()
    send_mail(request, to, frm,
              "I-D Resurrection Request",
              "idrfc/resurrect_request_email.txt",
              dict(doc=doc,
                   by=frm,
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url()))

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    email_resurrect_requested = email_resurrect_requestedREDESIGN

def email_resurrection_completed(request, doc):
    to = u"%s <%s>" % doc.idinternal.resurrect_requested_by.person.email()
    frm = "I-D Administrator <internet-drafts-reply@ietf.org>"
    send_mail(request, to, frm,
              "I-D Resurrection Completed - %s" % doc.file_tag(),
              "idrfc/resurrect_completed_email.txt",
              dict(doc=doc,
                   by=frm,
                   url=settings.IDTRACKER_BASE_URL + doc.idinternal.get_absolute_url()))

def email_resurrection_completedREDESIGN(request, doc, requester):
    to = requester.formatted_email()
    frm = "I-D Administrator <internet-drafts-reply@ietf.org>"
    send_mail(request, to, frm,
              "I-D Resurrection Completed - %s" % doc.file_tag(),
              "idrfc/resurrect_completed_email.txt",
              dict(doc=doc,
                   by=frm,
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url()))

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    email_resurrection_completed = email_resurrection_completedREDESIGN

def email_ballot_deferred(request, doc, by, telechat_date):
    to = "iesg@ietf.org"
    frm = "DraftTracker Mail System <iesg-secretary@ietf.org>"
    send_mail(request, to, frm,
              "IESG Deferred Ballot notification: %s" % doc.file_tag(),
              "idrfc/ballot_deferred_email.txt",
              dict(doc=doc,
                   by=by,
                   telechat_date=telechat_date))

def generate_issue_ballot_mail(request, doc):
    full_status = full_intended_status(doc.intended_status)
    status = full_status.replace("a ", "").replace("an ", "")

    ads = IESGLogin.objects.filter(user_level__in=(IESGLogin.AD_LEVEL, IESGLogin.INACTIVE_AD_LEVEL)).order_by('user_level', 'last_name')
    positions = dict((p.ad_id, p) for p in doc.idinternal.ballot.positions.all())
    
    # format positions
    ad_positions = []
    for ad in ads:
        p = positions.get(ad.id)
        if not p:
            continue

        def formatted(val):
            if val > 0:
                return "[ X ]"
            elif val < 0:
                return "[ . ]"
            else:
                return "[   ]"

        fmt = u"%-21s%-10s%-11s%-9s%-10s" % (
            unicode(ad)[:21],
            formatted(p.yes),
            formatted(p.noobj),
            formatted(p.discuss),
            "[ R ]" if p.recuse else formatted(p.abstain),
            )
        ad_positions.append((ad, fmt))
        
    active_ad_positions = filter(lambda t: t[0].user_level == IESGLogin.AD_LEVEL, ad_positions)
    inactive_ad_positions = filter(lambda t: t[0].user_level == IESGLogin.INACTIVE_AD_LEVEL, ad_positions)

    # arrange discusses and comments
    ad_feedback = []
    discusses = dict((p.ad_id, p) for p in doc.idinternal.ballot.discusses.all()
                     if p.ad_id in positions and positions[p.ad_id].discuss == 1)
    comments = dict((p.ad_id, p) for p in doc.idinternal.ballot.comments.all())
    for ad in ads:
        d = discusses.get(ad.id)
        c = comments.get(ad.id)
        if ad.user_level != IESGLogin.AD_LEVEL or not (c or d):
            continue

        ad_feedback.append((ad, d, c))
    
    return render_to_string("idrfc/issue_ballot_mail.txt",
                            dict(doc=doc,
                                 doc_url=settings.IDTRACKER_BASE_URL + doc.idinternal.get_absolute_url(),
                                 status=status,
                                 active_ad_positions=active_ad_positions,
                                 inactive_ad_positions=inactive_ad_positions,
                                 ad_feedback=ad_feedback
                                 )
                            )

def generate_issue_ballot_mailREDESIGN(request, doc):
    full_status = full_intended_status(doc.intended_std_level.name)
    status = full_status.replace("a ", "").replace("an ", "")

    active_ads = Person.objects.filter(role__name="ad", role__group__state="active").distinct()
    
    e = doc.latest_event(type="started_iesg_process")
    positions = BallotPositionDocEvent.objects.filter(doc=doc, type="changed_ballot_position", time__gte=e.time).order_by("-time", '-id').select_related('ad')

    # format positions and setup discusses and comments
    ad_feedback = []
    seen = set()
    active_ad_positions = []
    inactive_ad_positions = []
    for p in positions:
        if p.ad in seen:
            continue

        seen.add(p.ad)
        
        def formatted(val):
            if val:
                return "[ X ]"
            else:
                return "[   ]"

        fmt = u"%-21s%-10s%-11s%-9s%-10s" % (
            p.ad.name[:21],
            formatted(p.pos_id == "yes"),
            formatted(p.pos_id == "noobj"),
            formatted(p.pos_id == "discuss"),
            "[ R ]" if p.pos_id == "recuse" else formatted(p.pos_id == "abstain"),
            )

        if p.ad in active_ads:
            active_ad_positions.append(fmt)
            if not p.pos_id == "discuss":
                p.discuss = ""
            if p.comment or p.discuss:
                ad_feedback.append(p)
        else:
            inactive_ad_positions.append(fmt)
        
    active_ad_positions.sort()
    inactive_ad_positions.sort()
    ad_feedback.sort(key=lambda p: p.ad.name)

    e = doc.latest_event(LastCallDocEvent, type="sent_last_call")
    last_call_expires = e.expires if e else None

    e = doc.latest_event(WriteupDocEvent, type="changed_ballot_approval_text")
    approval_text = e.text if e else ""

    e = doc.latest_event(WriteupDocEvent, type="changed_ballot_writeup_text")
    ballot_writeup = e.text if e else ""

    # NOTE: according to Michelle Cotton <michelle.cotton@icann.org>
    # (as per 2011-10-24) IANA is scraping these messages for
    # information so would like to know beforehand if the format
    # changes (perhaps RFC 6359 will change that)
    return render_to_string("idrfc/issue_ballot_mailREDESIGN.txt",
                            dict(doc=doc,
                                 doc_url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url(),
                                 status=status,
                                 active_ad_positions=active_ad_positions,
                                 inactive_ad_positions=inactive_ad_positions,
                                 ad_feedback=ad_feedback,
                                 last_call_expires=last_call_expires,
                                 approval_text=approval_text,
                                 ballot_writeup=ballot_writeup,
                                 )
                            )

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    generate_issue_ballot_mail = generate_issue_ballot_mailREDESIGN

def email_iana(request, doc, to, msg):
    # fix up message and send message to IANA for each in ballot set
    import email
    parsed_msg = email.message_from_string(msg.encode("utf-8"))

    for i in doc.idinternal.ballot_set():
        extra = {}
        extra["Reply-To"] = "noreply@ietf.org"
        extra["X-IETF-Draft-string"] = i.document().filename
        extra["X-IETF-Draft-revision"] = i.document().revision_display()
    
        send_mail_text(request, "To: IANA <%s>" % to,
                       parsed_msg["From"], parsed_msg["Subject"],
                       parsed_msg.get_payload(),
                       extra=extra,
                       bcc="fenner@research.att.com")

def email_ianaREDESIGN(request, doc, to, msg):
    # fix up message and send it with extra info on doc in headers
    import email
    parsed_msg = email.message_from_string(msg.encode("utf-8"))

    extra = {}
    extra["Reply-To"] = "noreply@ietf.org"
    extra["X-IETF-Draft-string"] = doc.name
    extra["X-IETF-Draft-revision"] = doc.rev
    
    send_mail_text(request, "IANA <%s>" % to,
                   parsed_msg["From"], parsed_msg["Subject"],
                   parsed_msg.get_payload(),
                   extra=extra,
                   bcc="fenner@research.att.com")

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    email_iana = email_ianaREDESIGN

def email_last_call_expired(doc):
    text = "IETF Last Call has ended, and the state has been changed to\n%s." % doc.idinternal.cur_state.state
    
    send_mail(None,
              "iesg@ietf.org",
              "DraftTracker Mail System <iesg-secretary@ietf.org>",
              "Last Call Expired: %s" % doc.file_tag(),
              "idrfc/change_notice.txt",
              dict(text=text,
                   doc=doc,
                   url=settings.IDTRACKER_BASE_URL + doc.idinternal.get_absolute_url()),
              cc="iesg-secretary@ietf.org")

def email_last_call_expiredREDESIGN(doc):
    text = "IETF Last Call has ended, and the state has been changed to\n%s." % doc.get_state("draft-iesg").name
    
    send_mail(None,
              "iesg@ietf.org",
              "DraftTracker Mail System <iesg-secretary@ietf.org>",
              "Last Call Expired: %s" % doc.file_tag(),
              "idrfc/change_notice.txt",
              dict(text=text,
                   doc=doc,
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url()),
              cc="iesg-secretary@ietf.org")

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    email_last_call_expired = email_last_call_expiredREDESIGN

