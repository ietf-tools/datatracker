from django.conf import settings
from django.core.urlresolvers import reverse as urlreverse
from django.contrib.sites.models import Site
from django.template.loader import render_to_string

from ietf.utils.mail import send_mail, send_mail_message
from ietf.doc.models import Document
from ietf.person.models import Person
from ietf.group.models import Role
from ietf.message.models import Message
from ietf.utils.accesstoken import generate_access_token

def submission_confirmation_email_list(submission):
    try:
        doc = Document.objects.get(name=submission.name)
        email_list = [i.author.formatted_email() for i in doc.documentauthor_set.all() if not i.author.invalid_address()]
    except Document.DoesNotExist:
        email_list = [u'"%s" <%s>' % (author["name"], author["email"])
                      for author in submission.authors_parsed() if author["email"]]
        if submission.submitter_parsed()["email"] and submission.submitter not in email_list:
            email_list.append(submission.submitter)
    return email_list

def send_submission_confirmation(request, submission):
    subject = 'Confirm submission of I-D %s' % submission.name
    from_email = settings.IDSUBMIT_FROM_EMAIL
    to_email = submission_confirmation_email_list(submission)

    confirm_url = settings.IDTRACKER_BASE_URL + urlreverse('submit_confirm_submission', kwargs=dict(submission_id=submission.pk, auth_token=generate_access_token(submission.auth_key)))
    status_url = settings.IDTRACKER_BASE_URL + urlreverse('submit_submission_status_by_hash', kwargs=dict(submission_id=submission.pk, access_token=submission.access_token()))
        
    send_mail(request, to_email, from_email, subject, 'submit/confirm_submission.txt', {
        'submission': submission,
        'confirm_url': confirm_url,
        'status_url': status_url,
    })

    return to_email

def send_full_url(request, submission):
    subject = 'Full URL for managing submission of draft %s' % submission.name
    from_email = settings.IDSUBMIT_FROM_EMAIL
    to_email = submission_confirmation_email_list(submission)
    url = settings.IDTRACKER_BASE_URL + urlreverse('submit_submission_status_by_hash', kwargs=dict(submission_id=submission.pk, access_token=submission.access_token()))

    send_mail(request, to_email, from_email, subject, 'submit/full_url.txt', {
        'submission': submission,
        'url': url,
    })

    return to_email

def send_approval_request_to_group(request, submission):
    subject = 'New draft waiting for approval: %s' % submission.name
    from_email = settings.IDSUBMIT_FROM_EMAIL
    to_email = [r.formatted_email() for r in Role.objects.filter(group=submission.group, name="chair").select_related("email", "person")]
    if not to_email:
        return to_email

    send_mail(request, to_email, from_email, subject, 'submit/approval_request.txt', {
        'submission': submission,
        'domain': Site.objects.get_current().domain,
    })

    return to_email

def send_manual_post_request(request, submission, errors):
    subject = u'Manual Post Requested for %s' % submission.name
    from_email = settings.IDSUBMIT_FROM_EMAIL
    to_email = settings.IDSUBMIT_TO_EMAIL

    cc = [submission.submitter]
    cc += [u'"%s" <%s>' % (author["name"], author["email"])
           for author in submission.authors_parsed() if author["email"]]
    if submission.group:
        cc += [r.formatted_email() for r in Role.objects.filter(group=submission.group, name="chair").select_related("email", "person")]
    cc = list(set(cc))

    send_mail(request, to_email, from_email, subject, 'submit/manual_post_request.txt', {
        'submission': submission,
        'url': settings.IDTRACKER_BASE_URL + urlreverse('submit_submission_status', kwargs=dict(submission_id=submission.pk)),
        'errors': errors,
    }, cc=cc)


def announce_to_lists(request, submission):
    m = Message()
    m.by = Person.objects.get(name="(System)")
    if request.user.is_authenticated():
        try:
            m.by = request.user.person
        except Person.DoesNotExist:
            pass
    m.subject = 'I-D Action: %s-%s.txt' % (submission.name, submission.rev)
    m.frm = settings.IDSUBMIT_ANNOUNCE_FROM_EMAIL
    m.to = settings.IDSUBMIT_ANNOUNCE_LIST_EMAIL
    if submission.group and submission.group.list_email:
        m.cc = submission.group.list_email
    m.body = render_to_string('submit/announce_to_lists.txt',
                              dict(submission=submission,
                                   settings=settings))
    m.save()
    m.related_docs.add(Document.objects.get(name=submission.name))

    send_mail_message(request, m)


def announce_new_version(request, submission, draft, state_change_msg):
    to_email = []
    if draft.notify:
        to_email.append(draft.notify)
    if draft.ad:
        to_email.append(draft.ad.role_email("ad").address)

    if draft.stream_id == "iab":
        to_email.append("IAB Stream <iab-stream@iab.org>")
    elif draft.stream_id == "ise":
        to_email.append("Independent Submission Editor <rfc-ise@rfc-editor.org>")
    elif draft.stream_id == "irtf":
        to_email.append("IRSG <irsg@irtf.org>")

    # if it has been sent to the RFC Editor, keep them in the loop
    if draft.get_state_slug("draft-rfceditor") is not None:
        to_email.append("RFC Editor <rfc-editor@rfc-editor.org>")

    active_ballot = draft.active_ballot()
    if active_ballot:
        for ad, pos in active_ballot.active_ad_positions().iteritems():
            if pos and pos.pos_id == "discuss":
                to_email.append(ad.role_email("ad").address)

    if to_email:
        subject = 'New Version Notification - %s-%s.txt' % (submission.name, submission.rev)
        from_email = settings.IDSUBMIT_ANNOUNCE_FROM_EMAIL
        send_mail(request, to_email, from_email, subject, 'submit/announce_new_version.txt',
                  {'submission': submission,
                   'msg': state_change_msg})

def announce_to_authors(request, submission):
    authors = [u'"%s" <%s>' % (author["name"], author["email"]) for author in submission.authors_parsed() if author["email"]]
    to_email = list(set(submission_confirmation_email_list(submission) + authors))
    from_email = settings.IDSUBMIT_ANNOUNCE_FROM_EMAIL
    subject = 'New Version Notification for %s-%s.txt' % (submission.name, submission.rev)
    if submission.group:
        group = submission.group.acronym
    elif submission.name.startswith('draft-iesg'):
        group = 'IESG'
    else:
        group = 'Individual Submission'
    send_mail(request, to_email, from_email, subject, 'submit/announce_to_authors.txt',
              {'submission': submission,
               'group': group})
