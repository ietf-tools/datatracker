# generation of mails 

import textwrap, datetime

from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.core.urlresolvers import reverse as urlreverse

from ietf.utils.mail import send_mail, send_mail_text
from ietf.ipr.utils import iprs_from_docs, related_docs
from ietf.doc.models import WriteupDocEvent, BallotPositionDocEvent, LastCallDocEvent, DocAlias, ConsensusDocEvent, DocTagName
from ietf.doc.utils import needed_ballot_positions
from ietf.person.models import Person
from ietf.group.models import Group, Role
from ietf.doc.models import Document

def email_state_changed(request, doc, text):
    to = [x.strip() for x in doc.notify.replace(';', ',').split(',')]
    if not to:
        return
    
    text = strip_tags(text)
    send_mail(request, to, None,
              "ID Tracker State Update Notice: %s" % doc.file_tag(),
              "doc/mail/state_changed_email.txt",
              dict(text=text,
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url()))

def email_stream_changed(request, doc, old_stream, new_stream, text=""):
    """Email the change text to the notify group and to the stream chairs"""
    to = [x.strip() for x in doc.notify.replace(';', ',').split(',')]

    # These use comprehension to deal with conditions when there might be more than one chair listed for a stream
    if old_stream:
        to.extend([r.formatted_email() for r in Role.objects.filter(group__acronym=old_stream.slug, name='chair')])
    if new_stream:
        to.extend([r.formatted_email() for r in Role.objects.filter(group__acronym=new_stream.slug, name='chair')])

    if not to:
        return
    
    if not text:
        text = u"Stream changed to <b>%s</b> from %s" % (new_stream, old_stream)
    text = strip_tags(text)

    send_mail(request, to, None,
              "ID Tracker Stream Change Notice: %s" % doc.file_tag(),
              "doc/mail/stream_changed_email.txt",
              dict(text=text,
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url()))

def email_pulled_from_rfc_queue(request, doc, comment, prev_state, next_state):
    extra=extra_automation_headers(doc)
    extra['Cc'] = 'iesg-secretary@ietf.org'
    send_mail(request, ["IANA <iana@iana.org>", "RFC Editor <rfc-editor@rfc-editor.org>"], None,
              "%s changed state from %s to %s" % (doc.name, prev_state.name, next_state.name),
              "doc/mail/pulled_from_rfc_queue_email.txt",
              dict(doc=doc,
                   prev_state=prev_state,
                   next_state=next_state,
                   comment=comment,
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url()),
              extra=extra)


def email_authors(request, doc, subject, text):
    to = [x.strip() for x in doc.author_list().split(',')]
    if not to:
        return
    
    send_mail_text(request, to, None, subject, text)

def html_to_text(html):
    return strip_tags(html.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").replace("<br>", "\n"))
    
def email_ad(request, doc, ad, changed_by, text, subject=None):
    if not ad or not changed_by or ad == changed_by:
        return

    to = ad.role_email("ad").formatted_email()
    send_mail(request, to,
              "DraftTracker Mail System <iesg-secretary@ietf.org>",
              "%s updated by %s" % (doc.file_tag(), changed_by.plain_name()),
              "doc/mail/change_notice.txt",
              dict(text=html_to_text(text),
                   doc=doc,
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url()))


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
    cc = []
    if doc.group.type_id in ("individ", "area"):
        group = "an individual submitter"
        expiration_date += datetime.timedelta(days=14)
    else:
        group = "the %s WG (%s)" % (doc.group.name, doc.group.acronym)
        if doc.group.list_email:
            cc.append(doc.group.list_email)

    doc.filled_title = textwrap.fill(doc.title, width=70, subsequent_indent=" " * 3)
    
    iprs = iprs_from_docs(related_docs(DocAlias.objects.get(name=doc.canonical_name())))
    if iprs:
        ipr_links = [ urlreverse("ietf.ipr.views.show", kwargs=dict(id=i.id)) for i in iprs]
        ipr_links = [ settings.IDTRACKER_BASE_URL+url if not url.startswith("http") else url for url in ipr_links ]
    else:
        ipr_links = None

    mail = render_to_string("doc/mail/last_call_announcement.txt",
                            dict(doc=doc,
                                 doc_url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url() + "ballot/",
                                 expiration_date=expiration_date.strftime("%Y-%m-%d"), #.strftime("%B %-d, %Y"),
                                 cc=", ".join("<%s>" % e for e in cc),
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

    cc = []
    cc.extend(settings.DOC_APPROVAL_EMAIL_CC)

    # the second check catches some area working groups (like
    # Transport Area Working Group)
    if doc.group.type_id not in ("area", "individ", "ag") and not doc.group.name.endswith("Working Group"):
        doc.group.name_with_wg = doc.group.name + " Working Group"
        if doc.group.list_email:
            cc.append("%s mailing list <%s>" % (doc.group.acronym, doc.group.list_email))
        cc.append("%s chair <%s-chairs@ietf.org>" % (doc.group.acronym, doc.group.acronym))
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
        
    return render_to_string("doc/mail/approval_mail.txt",
                            dict(doc=doc,
                                 docs=[doc],
                                 doc_url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url(),
                                 cc=",\n    ".join(cc),
                                 doc_type=doc_type,
                                 made_by=made_by,
                                 contacts=contacts,
                                 action_type=action_type,
                                 )
                            )

def generate_approval_mail_rfc_editor(request, doc):
    disapproved = doc.get_state_slug("draft-iesg") in DO_NOT_PUBLISH_IESG_STATES
    doc_type = "RFC" if doc.get_state_slug() == "rfc" else "Internet Draft"

    to = []
    if doc.group.type_id != "individ":
        for r in doc.group.role_set.filter(name="chair").select_related():
            to.append(r.formatted_email())

    if doc.stream_id in ("ise", "irtf"):
        # include ISE/IRTF chairs
        g = Group.objects.get(acronym=doc.stream_id)
        for r in g.role_set.filter(name="chair").select_related():
            to.append(r.formatted_email())

    if doc.stream_id == "irtf":
        # include IRSG
        to.append('"Internet Research Steering Group" <irsg@irtf.org>')

    return render_to_string("doc/mail/approval_mail_rfc_editor.txt",
                            dict(doc=doc,
                                 doc_url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url(),
                                 doc_type=doc_type,
                                 disapproved=disapproved,
                                 to=", ".join(to),
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
    to = "iesg-secretary@ietf.org"
    frm = '"DraftTracker Mail System" <iesg-secretary@ietf.org>'
    
    send_mail(request, to, frm,
              "Last Call: %s" % doc.file_tag(),
              "doc/mail/last_call_request.txt",
              dict(docs=[doc],
                   doc_url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url()))

def email_resurrect_requested(request, doc, by):
    to = "I-D Administrator <internet-drafts@ietf.org>"

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
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url()))

def email_resurrection_completed(request, doc, requester):
    if requester.role_set.filter(name="secr", group__acronym="secretariat"):
        e = requester.role_email("secr", group="secretariat")
    else:
        e = requester.role_email("ad")

    to = e.formatted_email()
    frm = "I-D Administrator <internet-drafts-reply@ietf.org>"
    send_mail(request, to, frm,
              "I-D Resurrection Completed - %s" % doc.file_tag(),
              "doc/mail/resurrect_completed_email.txt",
              dict(doc=doc,
                   by=frm,
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url()))

def email_ballot_deferred(request, doc, by, telechat_date):
    to = "iesg@ietf.org"
    frm = "DraftTracker Mail System <iesg-secretary@ietf.org>"
    send_mail(request, to, frm,
              "IESG Deferred Ballot notification: %s" % doc.file_tag(),
              "doc/mail/ballot_deferred_email.txt",
              dict(doc=doc,
                   by=by,
                   action='deferred',
                   telechat_date=telechat_date))

def email_ballot_undeferred(request, doc, by, telechat_date):
    to = "iesg@ietf.org"
    frm = "DraftTracker Mail System <iesg-secretary@ietf.org>"
    send_mail(request, to, frm,
              "IESG Undeferred Ballot notification: %s" % doc.file_tag(),
              "doc/mail/ballot_deferred_email.txt",
              dict(doc=doc,
                   by=by,
                   action='undeferred',
                   telechat_date=telechat_date))

def generate_issue_ballot_mail(request, doc, ballot):
    active_ads = Person.objects.filter(role__name="ad", role__group__state="active", role__group__type="area").distinct()
    
    positions = BallotPositionDocEvent.objects.filter(doc=doc, type="changed_ballot_position", ballot=ballot).order_by("-time", '-id').select_related('ad')

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
            p.ad.plain_name()[:21],
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
    ad_feedback.sort(key=lambda p: p.ad.plain_name())

    e = doc.latest_event(LastCallDocEvent, type="sent_last_call")
    last_call_expires = e.expires if e else None

    e = doc.latest_event(WriteupDocEvent, type="changed_ballot_approval_text")
    approval_text = e.text if e else ""

    e = doc.latest_event(WriteupDocEvent, type="changed_ballot_writeup_text")
    ballot_writeup = e.text if e else ""

    return render_to_string("doc/mail/issue_ballot_mail.txt",
                            dict(doc=doc,
                                 doc_url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url(),
                                 active_ad_positions=active_ad_positions,
                                 inactive_ad_positions=inactive_ad_positions,
                                 ad_feedback=ad_feedback,
                                 last_call_expires=last_call_expires,
                                 approval_text=approval_text,
                                 ballot_writeup=ballot_writeup,
                                 needed_ballot_positions=
                                   needed_ballot_positions(doc,
                                     doc.active_ballot().active_ad_positions().values()
                                   ),
                                 )
                            )

def email_iana(request, doc, to, msg):
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
                   extra=extra)

def extra_automation_headers(doc):
    extra = {}
    extra["X-IETF-Draft-string"] = doc.name
    extra["X-IETF-Draft-revision"] = doc.rev

    return extra

def email_last_call_expired(doc):
    text = "IETF Last Call has ended, and the state has been changed to\n%s." % doc.get_state("draft-iesg").name
    
    to = [x.strip() for x in doc.notify.replace(';', ',').split(',')]
    to.insert(0, "iesg@ietf.org")

    send_mail(None,
              to,
              "DraftTracker Mail System <iesg-secretary@ietf.org>",
              "Last Call Expired: %s" % doc.file_tag(),
              "doc/mail/change_notice.txt",
              dict(text=text,
                   doc=doc,
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url()),
              cc="iesg-secretary@ietf.org")

def stream_state_email_recipients(doc, extra_recipients=[]):
    persons = set()
    res = []
    for r in Role.objects.filter(group=doc.group, name__in=("chair", "delegate")).select_related("person", "email"):
        res.append(r.formatted_email())
        persons.add(r.person)

    for email in doc.authors.all():
        if email.person not in persons:
            res.append(email.formatted_email())
            persons.add(email.person)

    for e in extra_recipients:
        if e.person not in persons:
            res.append(e.formatted_email())
            persons.add(e.person)

    return res

def email_stream_state_changed(request, doc, prev_state, new_state, by, comment=""):
    recipients = stream_state_email_recipients(doc)

    state_type = (prev_state or new_state).type

    send_mail(request, recipients, settings.DEFAULT_FROM_EMAIL,
              u"%s changed for %s" % (state_type.label, doc.name),
              'doc/mail/stream_state_changed_email.txt',
              dict(doc=doc,
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url(),
                   state_type=state_type,
                   prev_state=prev_state,
                   new_state=new_state,
                   by=by,
                   comment=comment))

def email_stream_tags_changed(request, doc, added_tags, removed_tags, by, comment=""):
    extra_recipients = []

    if DocTagName.objects.get(slug="sheph-u") in added_tags and doc.shepherd:
        extra_recipients.append(doc.shepherd)

    recipients = stream_state_email_recipients(doc, extra_recipients)

    send_mail(request, recipients, settings.DEFAULT_FROM_EMAIL,
              u"Tags changed for %s" % doc.name,
              'doc/mail/stream_tags_changed_email.txt',
              dict(doc=doc,
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url(),
                   added=added_tags,
                   removed=removed_tags,
                   by=by,
                   comment=comment))

def send_review_possibly_replaces_request(request, doc):
    to_email = []

    if doc.stream_id == "ietf":
        to_email.extend(r.formatted_email() for r in Role.objects.filter(group=doc.group, name="chair").select_related("email", "person"))
    elif doc.stream_id == "iab":
        to_email.append("IAB Stream <iab-stream@iab.org>")
    elif doc.stream_id == "ise":
        to_email.append("Independent Submission Editor <rfc-ise@rfc-editor.org>")
    elif doc.stream_id == "irtf":
        to_email.append("IRSG <irsg@irtf.org>")

    possibly_replaces = Document.objects.filter(name__in=[alias.name for alias in doc.related_that_doc("possibly-replaces")])
    other_chairs = Role.objects.filter(group__in=[other.group for other in possibly_replaces], name="chair").select_related("email", "person")
    to_email.extend(r.formatted_email() for r in other_chairs)

    if not to_email:
        to_email.append("internet-drafts@ietf.org")

    if to_email:
        send_mail(request, list(set(to_email)), settings.DEFAULT_FROM_EMAIL,
                  'Review of suggested possible replacements for %s-%s needed' % (doc.name, doc.rev),
                  'doc/mail/review_possibly_replaces_request.txt', {
                      'doc': doc,
                      'possibly_replaces': doc.related_that_doc("possibly-replaces"),
                      'review_url': settings.IDTRACKER_BASE_URL + urlreverse("doc_review_possibly_replaces", kwargs={ "name": doc.name }),
                  })
