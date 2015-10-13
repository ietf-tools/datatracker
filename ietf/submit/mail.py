from django.conf import settings
from django.core.urlresolvers import reverse as urlreverse
from django.contrib.sites.models import Site
from django.template.loader import render_to_string

from ietf.utils.mail import send_mail, send_mail_message
from ietf.doc.models import Document
from ietf.person.models import Person
from ietf.message.models import Message
from ietf.utils.accesstoken import generate_access_token
from ietf.mailtrigger.utils import gather_address_lists

def send_submission_confirmation(request, submission):
    subject = 'Confirm submission of I-D %s' % submission.name
    from_email = settings.IDSUBMIT_FROM_EMAIL
    (to_email, cc) = gather_address_lists('sub_confirmation_requested',submission=submission)

    confirm_url = settings.IDTRACKER_BASE_URL + urlreverse('submit_confirm_submission', kwargs=dict(submission_id=submission.pk, auth_token=generate_access_token(submission.auth_key)))
    status_url = settings.IDTRACKER_BASE_URL + urlreverse('submit_submission_status_by_hash', kwargs=dict(submission_id=submission.pk, access_token=submission.access_token()))
        
    send_mail(request, to_email, from_email, subject, 'submit/confirm_submission.txt', 
              {
                'submission': submission,
                'confirm_url': confirm_url,
                'status_url': status_url,
              },
              cc=cc)

    all_addrs = to_email
    all_addrs.extend(cc)
    return all_addrs

def send_full_url(request, submission):
    subject = 'Full URL for managing submission of draft %s' % submission.name
    from_email = settings.IDSUBMIT_FROM_EMAIL
    (to_email, cc) = gather_address_lists('sub_management_url_requested',submission=submission)
    url = settings.IDTRACKER_BASE_URL + urlreverse('submit_submission_status_by_hash', kwargs=dict(submission_id=submission.pk, access_token=submission.access_token()))

    send_mail(request, to_email, from_email, subject, 'submit/full_url.txt', 
              {
                'submission': submission,
                'url': url,
              },
              cc=cc)

    all_addrs = to_email
    all_addrs.extend(cc)
    return all_addrs

def send_approval_request_to_group(request, submission):
    subject = 'New draft waiting for approval: %s' % submission.name
    from_email = settings.IDSUBMIT_FROM_EMAIL
    (to_email,cc) = gather_address_lists('sub_chair_approval_requested',submission=submission)
    if not to_email:
        return to_email

    send_mail(request, to_email, from_email, subject, 'submit/approval_request.txt', 
              {
                'submission': submission,
                'domain': Site.objects.get_current().domain,
              },
              cc=cc)
    all_addrs = to_email
    all_addrs.extend(cc)
    return all_addrs

def send_manual_post_request(request, submission, errors):
    subject = u'Manual Post Requested for %s' % submission.name
    from_email = settings.IDSUBMIT_FROM_EMAIL
    (to_email,cc) = gather_address_lists('sub_manual_post_requested',submission=submission)
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
    (m.to, m.cc) = gather_address_lists('sub_announced',submission=submission)
    m.body = render_to_string('submit/announce_to_lists.txt',
                              dict(submission=submission,
                                   settings=settings))
    m.save()
    m.related_docs.add(Document.objects.get(name=submission.name))

    send_mail_message(request, m)


def announce_new_version(request, submission, draft, state_change_msg):
    (to_email,cc) = gather_address_lists('sub_new_version',doc=draft,submission=submission)

    if to_email:
        subject = 'New Version Notification - %s-%s.txt' % (submission.name, submission.rev)
        from_email = settings.IDSUBMIT_ANNOUNCE_FROM_EMAIL
        send_mail(request, to_email, from_email, subject, 'submit/announce_new_version.txt',
                  {'submission': submission,
                   'msg': state_change_msg},
                  cc=cc)

def announce_to_authors(request, submission):
    (to_email, cc) = gather_address_lists('sub_announced_to_authors',submission=submission)
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
               'group': group},
              cc=cc)
