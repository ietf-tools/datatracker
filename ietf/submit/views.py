# Copyright The IETF Trust 2007, All Rights Reserved
from django.conf import settings
from django.core.urlresolvers import reverse
from django.contrib.sites.models import Site
from django.http import HttpResponseRedirect, Http404, HttpResponseForbidden, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.core.exceptions import ObjectDoesNotExist

from ietf.submit.models import IdSubmissionDetail, IdApprovedDetail
from ietf.submit.forms import UploadForm, AutoPostForm, MetaDataForm
from ietf.submit.utils import (DraftValidation, perform_post, remove_docs,
                               get_person_for_user, is_secretariat,
                               request_full_url, UPLOADED,
                               WAITING_AUTHENTICATION, CANCELED,
                               INITIAL_VERSION_APPROVAL_REQUESTED,
                               MANUAL_POST_REQUESTED, POSTED)
from ietf.utils.mail import send_mail


def submit_index(request):
    if request.method == 'POST':
        try:
            form = UploadForm(request=request, data=request.POST, files=request.FILES)
            if form.is_valid():
                submit = form.save()
                return HttpResponseRedirect(reverse(draft_status, None, kwargs={'submission_id': submit.submission_id, 'submission_hash': submit.get_hash()}))
        except IOError:
            form = UploadForm(request=request)
    else:
        form = UploadForm(request=request)
    return render_to_response('submit/submit_index.html',
                              {'selected': 'index',
                               'form': form},
                              context_instance=RequestContext(request))


def submit_status(request):
    error = None
    filename = None
    if request.method == 'POST':
        filename = request.POST.get('filename', '')
        detail = IdSubmissionDetail.objects.filter(filename=filename).order_by('-pk')
        if detail:
            return HttpResponseRedirect(reverse(draft_status, None, kwargs={'submission_id': detail[0].submission_id}))
        error = 'No valid history found for %s' % filename
    return render_to_response('submit/submit_status.html',
                              {'selected': 'status',
                               'error': error,
                               'filename': filename},
                              context_instance=RequestContext(request))


def _can_approve(user, detail):
    person = get_person_for_user(user)
    if detail.status_id != INITIAL_VERSION_APPROVAL_REQUESTED or not detail.group_acronym:
        return None
    if person in [i.person for i in detail.group_acronym.wgchair_set.all()] or is_secretariat(user):
        return True
    return False


def _can_force_post(user, detail):
    if detail.status_id not in [MANUAL_POST_REQUESTED,
            WAITING_AUTHENTICATION, INITIAL_VERSION_APPROVAL_REQUESTED]:
        return None
    if is_secretariat(user):
        return True
    return False

def _can_cancel(user, detail, submission_hash):
    if detail.status_id in [CANCELED, POSTED]:
        return None
    if is_secretariat(user):
        return True
    if submission_hash and detail.get_hash() == submission_hash:
        return True
    return False

def _can_edit(user, detail, submission_hash):
    if detail.status_id != UPLOADED:
        return None
    if is_secretariat(user):
        return True
    if submission_hash and detail.get_hash() == submission_hash:
        return True
    return False

def draft_status(request, submission_id, submission_hash=None, message=None):
    detail = get_object_or_404(IdSubmissionDetail, submission_id=submission_id)
    if submission_hash and not detail.get_hash() == submission_hash:
        raise Http404
    validation = DraftValidation(detail)
    is_valid = validation.is_valid()
    status = None
    allow_edit = _can_edit(request.user, detail, submission_hash)
    can_force_post = _can_force_post(request.user, detail)
    can_approve = _can_approve(request.user, detail)
    can_cancel = _can_cancel(request.user, detail, submission_hash)
    if detail.status_id != UPLOADED:
        if detail.status_id == CANCELED:
            message = ('error', 'This submission has been canceled, modification is no longer possible')
        status = detail.status
        allow_edit = None

    if request.method == 'POST' and allow_edit:
        if request.POST.get('autopost', False):
            auto_post_form = AutoPostForm(draft=detail, validation=validation, data=request.POST)
            if auto_post_form.is_valid():
                try:
                    approved_detail = IdApprovedDetail.objects.get(filename=detail.filename)
                except ObjectDoesNotExist:
                    approved_detail = None
                if detail.group_acronym and not approved_detail:
                    detail.status_id = INITIAL_VERSION_APPROVAL_REQUESTED
                    detail.save()
                else:
                    approved_detail = True

                if detail.revision == '00' and not approved_detail:
                    submitter = auto_post_form.save_submitter_info()
                    subject = 'New draft waiting for approval: %s' % detail.filename
                    from_email = settings.IDSUBMIT_FROM_EMAIL
                    to_email = []
                    if detail.group_acronym:
                        to_email += [i.person.email()[1] for i in detail.group_acronym.wgchair_set.all()]
                    to_email = list(set(to_email))
                    if to_email:
                        metadata_form = MetaDataForm(draft=detail, validation=validation)
                        send_mail(request, to_email, from_email, subject, 'submit/submission_approval.txt',
                                  {'submitter': submitter, 'form': metadata_form,
                                   'draft': detail, 'domain': Site.objects.get_current().domain})
                    return HttpResponseRedirect(reverse(draft_status, None, kwargs={'submission_id': detail.submission_id}))
                else:
                    auto_post_form.save(request)
                    detail = get_object_or_404(IdSubmissionDetail, submission_id=submission_id)
                    validation = DraftValidation(detail)
                    is_valid = validation.is_valid()
                    status = detail.status
                    can_force_post = _can_force_post(request.user, detail)
                    can_approve = _can_approve(request.user, detail)
                    can_cancel = _can_cancel(request.user, detail, submission_hash)
                    allow_edit = None
                    message = ('success', 'Your submission is pending email authentication. An email has been sent you with instructions.')
        else:
            return HttpResponseRedirect(reverse(draft_edit, None, kwargs={'submission_id': detail.submission_id, 'submission_hash': submission_hash}))
    else:
        auto_post_form = AutoPostForm(draft=detail, validation=validation)

    show_notify_button = False
    if allow_edit == False or can_cancel == False:
        show_notify_button = True
    return render_to_response('submit/draft_status.html',
                              {'selected': 'status',
                               'detail': detail,
                               'validation': validation,
                               'auto_post_form': auto_post_form,
                               'is_valid': is_valid,
                               'status': status,
                               'message': message,
                               'allow_edit': allow_edit,
                               'can_force_post': can_force_post,
                               'can_approve': can_approve,
                               'can_cancel': can_cancel,
                               'submission_hash': submission_hash,
                               'show_notify_button': show_notify_button,
                              },
                              context_instance=RequestContext(request))


def draft_cancel(request, submission_id, submission_hash=None):
    if request.method!='POST':
        return HttpResponseNotAllowed(['POST'])
    detail = get_object_or_404(IdSubmissionDetail, submission_id=submission_id)
    can_cancel = _can_cancel(request.user, detail, submission_hash)
    if not can_cancel:
        if can_cancel == None:
            raise Http404
        return HttpResponseForbidden('You have no permission to perform this action')
    detail.status_id = CANCELED
    detail.save()
    remove_docs(detail)
    return HttpResponseRedirect(reverse(draft_status, None, kwargs={'submission_id': submission_id}))


def draft_edit(request, submission_id, submission_hash=None):
    detail = get_object_or_404(IdSubmissionDetail, submission_id=submission_id)
    can_edit = _can_edit(request.user, detail, submission_hash)
    if not can_edit:
        if can_edit == None:
            raise Http404
        return HttpResponseForbidden('You have no permission to perform this action')
    validation = DraftValidation(detail)
    validation.validate_wg()
    if request.method == 'POST':
        form = MetaDataForm(draft=detail, validation=validation, data=request.POST)
        if form.is_valid():
            form.save(request)
            return HttpResponseRedirect(reverse(draft_status, None, kwargs={'submission_id': detail.submission_id}))
    else:
        form = MetaDataForm(draft=detail, validation=validation)
    return render_to_response('submit/draft_edit.html',
                              {'selected': 'status',
                               'detail': detail,
                               'validation': validation,
                               'form': form,
                              },
                              context_instance=RequestContext(request))


def draft_confirm(request, submission_id, auth_key):
    detail = get_object_or_404(IdSubmissionDetail, submission_id=submission_id)
    message = None
    if auth_key != detail.auth_key:
        message = ('error', 'Incorrect authorization key')
    elif detail.status_id != WAITING_AUTHENTICATION:
        message = ('error', 'The submission can not be autoposted because it is in state: %s' % detail.status.status_value)
    else:
        if request.method=='POST':
            message = ('success', 'Authorization key accepted. Auto-Post complete')
            perform_post(detail)
        else:
            return render_to_response('submit/last_confirmation_step.html',
                               {'detail': detail, },
                               context_instance=RequestContext(request))
    return draft_status(request, submission_id, message=message)


def draft_approve(request, submission_id, check_function=_can_approve):
    if request.method!='POST':
        return HttpResponseNotAllowed(['POST'])
    detail = get_object_or_404(IdSubmissionDetail, submission_id=submission_id)
    can_perform = check_function(request.user, detail)
    if not can_perform:
        if can_perform == None:
            raise Http404
        return HttpResponseForbidden('You have no permission to perform this action')
    perform_post(detail)
    return HttpResponseRedirect(reverse(draft_status, None, kwargs={'submission_id': submission_id}))


def draft_force(request, submission_id):
    if request.method!='POST':
        return HttpResponseNotAllowed(['POST'])
    return draft_approve(request, submission_id, check_function=_can_force_post)


def full_url_request(request, submission_id):
    if request.method!='POST':
        return HttpResponseNotAllowed(['POST'])
    detail = get_object_or_404(IdSubmissionDetail, submission_id=submission_id)
    request_full_url(request, detail)
    message = ('success', 'An email has been sent to draft authors to inform them of the full access url')
    return draft_status(request, submission_id, message=message)
