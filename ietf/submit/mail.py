# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-

import os

from django.conf import settings
from django.urls import reverse as urlreverse
from django.contrib.sites.models import Site
from django.template.loader import render_to_string

import debug                            # pyflakes:ignore

from ietf.utils.mail import send_mail, send_mail_message
from ietf.doc.models import Document
from ietf.person.models import Person
from ietf.message.models import Message
from ietf.utils.accesstoken import generate_access_token
from ietf.mailtrigger.utils import gather_address_lists
from ietf.submit.checkers import DraftIdnitsChecker


def send_submission_confirmation(request, submission, chair_notice=False):
    subject = 'Confirm submission of I-D %s' % submission.name
    from_email = settings.IDSUBMIT_FROM_EMAIL
    (to_email, cc) = gather_address_lists('sub_confirmation_requested',submission=submission)

    confirmation_url = settings.IDTRACKER_BASE_URL + urlreverse('ietf.submit.views.confirm_submission', kwargs=dict(submission_id=submission.pk, auth_token=generate_access_token(submission.auth_key)))
    status_url = settings.IDTRACKER_BASE_URL + urlreverse('ietf.submit.views.submission_status', kwargs=dict(submission_id=submission.pk, access_token=submission.access_token()))
        
    send_mail(request, to_email, from_email, subject, 'submit/confirm_submission.txt', 
              {
                'submission': submission,
                'confirmation_url': confirmation_url,
                'status_url': status_url,
                'chair_notice': chair_notice,
              },
              cc=cc)

    all_addrs = to_email
    all_addrs.extend(cc)
    return all_addrs

def send_full_url(request, submission):
    subject = 'Full URL for managing submission of Internet-Draft %s' % submission.name
    from_email = settings.IDSUBMIT_FROM_EMAIL
    (to_email, cc) = gather_address_lists('sub_management_url_requested',submission=submission)
    url = settings.IDTRACKER_BASE_URL + urlreverse('ietf.submit.views.submission_status', kwargs=dict(submission_id=submission.pk, access_token=submission.access_token()))

    send_mail(request, to_email, from_email, subject, 'submit/full_url.txt', 
              {
                'submission': submission,
                'url': url,
              },
              cc=cc)

    all_addrs = to_email
    all_addrs.extend(cc)
    return all_addrs


def send_approval_request(request, submission, replaced_doc=None):
    """Send an approval request for a submission
    
    If replaced_doc is not None, requests will be sent to the wg chairs or ADs
    responsible for that doc's group instead of the submission. 
    """
    subject = 'New Internet-Draft waiting for approval: %s' % submission.name
    from_email = settings.IDSUBMIT_FROM_EMAIL

    # Sort out which MailTrigger to use
    mt_kwargs = dict(submission=submission)
    if replaced_doc:
        mt_kwargs['doc'] = replaced_doc
    if submission.state_id == 'ad-appr':
        approval_type = 'ad'
        if replaced_doc:
            mt_slug = 'sub_replaced_doc_director_approval_requested'
        else:
            mt_slug = 'sub_director_approval_requested'
    else:
        approval_type = 'chair'
        if replaced_doc:
            mt_slug = 'sub_replaced_doc_chair_approval_requested'
        else:
            mt_slug = 'sub_chair_approval_requested'

    (to_email,cc) = gather_address_lists(mt_slug, **mt_kwargs)
    if not to_email:
        return to_email

    send_mail(request, to_email, from_email, subject, 'submit/approval_request.txt',
              {
                  'submission': submission,
                  'domain': Site.objects.get_current().domain,
                  'approval_type': approval_type,
              },
              cc=cc)
    all_addrs = to_email
    all_addrs.extend(cc)
    return all_addrs


def send_manual_post_request(request, submission, errors):
    subject = 'Manual Post Requested for %s' % submission.name
    from_email = settings.IDSUBMIT_FROM_EMAIL
    (to_email,cc) = gather_address_lists('sub_manual_post_requested',submission=submission)
    checker = DraftIdnitsChecker(options=[]) # don't use the default --submitcheck limitation
    file_name = os.path.join(settings.IDSUBMIT_STAGING_PATH, '%s-%s.txt' % (submission.name, submission.rev))
    nitspass, nitsmsg, nitserr, nitswarn, nitsresult = checker.check_file_txt(file_name)
    send_mail(request, to_email, from_email, subject, 'submit/manual_post_request.txt', {
        'submission': submission,
        'url': settings.IDTRACKER_BASE_URL + urlreverse('ietf.submit.views.submission_status', kwargs=dict(submission_id=submission.pk)),
        'errors': errors,
        'idnits': nitsmsg,
    }, cc=cc)


def announce_to_lists(request, submission):
    m = Message()
    m.by = Person.objects.get(name="(System)")
    if request.user.is_authenticated:
        try:
            m.by = request.user.person
        except Person.DoesNotExist:
            pass
    m.subject = 'I-D Action: %s-%s.txt' % (submission.name, submission.rev)
    m.frm = settings.IDSUBMIT_ANNOUNCE_FROM_EMAIL
    (m.to, m.cc) = gather_address_lists('sub_announced',submission=submission).as_strings()
    if m.cc:
        m.reply_to = m.cc
    m.body = render_to_string('submit/announce_to_lists.txt',
                              dict(submission=submission,
                                   settings=settings))
    m.save()
    m.related_docs.add(Document.objects.get(name=submission.name))

    send_mail_message(request, m)


def announce_new_wg_00(request, submission):
    m = Message()
    m.by = Person.objects.get(name="(System)")
    if request.user.is_authenticated:
        try:
            m.by = request.user.person
        except Person.DoesNotExist:
            pass
    m.subject = 'I-D Action: %s-%s.txt' % (submission.name, submission.rev)
    m.frm = settings.IDSUBMIT_ANNOUNCE_FROM_EMAIL
    (m.to, m.cc) = gather_address_lists('sub_new_wg_00',submission=submission).as_strings()
    if m.cc:
        m.reply_to = m.cc
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

