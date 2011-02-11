# Copyright The IETF Trust 2007, All Rights Reserved
from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import get_object_or_404
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.core.exceptions import ObjectDoesNotExist

from ietf.submit.models import IdSubmissionDetail, IdApprovedDetail
from ietf.submit.forms import UploadForm, AutoPostForm, MetaDataForm
from ietf.submit.utils import (DraftValidation, perform_post,
                               UPLOADED, WAITING_AUTHENTICATION, CANCELED, INITIAL_VERSION_APPROVAL_REQUESTED)
from ietf.utils.mail import send_mail



def submit_index(request):
    if request.method == 'POST':
        form = UploadForm(request=request, data=request.POST, files=request.FILES)
        if form.is_valid():
            submit = form.save()
            return HttpResponseRedirect(reverse(draft_status, None, kwargs={'submission_id': submit.submission_id}))
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
        detail = IdSubmissionDetail.objects.filter(filename=filename)
        if detail:
            return HttpResponseRedirect(reverse(draft_status, None, kwargs={'submission_id': detail[0].submission_id}))
        error = 'No valid history found for %s' % filename
    return render_to_response('submit/submit_status.html', 
                              {'selected': 'status',
                               'error': error,
                               'filename': filename},
                              context_instance=RequestContext(request))
    


def draft_status(request, submission_id, message=None):
    detail = get_object_or_404(IdSubmissionDetail, submission_id=submission_id)
    validation = DraftValidation(detail)
    is_valid = validation.is_valid()
    status = None
    allow_edit = True
    if detail.status_id != UPLOADED:
        if detail.status_id == CANCELED:
            message=('error', 'This submission has been canceled, modification is no longer possible')
        status = detail.status
        allow_edit = None

    if request.method=='POST' and allow_edit:
        if request.POST.get('autopost', False):
            try:
                approved_detail = IdApprovedDetail.objects.get(filename=detail.filename)
            except ObjectDoesNotExist:
                approved_detail = None
                detail.status_id = INITIAL_VERSION_APPROVAL_REQUESTED
                detail.save()

            if detail.revision == '00' and not approved_detail:
                subject = 'New draft waiting for approval: %s' % detail.filename
                from_email = settings.IDST_FROM_EMAIL
                to_email = []
                if detail.group_acronym:
                    to_email += [i.person.email()[1] for i in detail.group_acronym.wgchair_set.all()]
                to_email = list(set(to_email))
                if to_email:
                    metadata_form = MetaDataForm(draft=detail, validation=validation)
                    send_mail(request, to_email, from_email, subject, 'submit/manual_post_mail.txt',
                              {'form': metadata_form, 'draft': detail})
            else:
                auto_post_form = AutoPostForm(draft=detail, validation=validation, data=request.POST)
                if auto_post_form.is_valid():
                    auto_post_form.save(request)
            return HttpResponseRedirect(reverse(draft_status, None, kwargs={'submission_id': detail.submission_id}))

        else:
            return HttpResponseRedirect(reverse(draft_edit, None, kwargs={'submission_id': detail.submission_id}))
    else:
        auto_post_form = AutoPostForm(draft=detail, validation=validation)
    return render_to_response('submit/draft_status.html', 
                              {'selected': 'status',
                               'detail': detail,
                               'validation': validation,
                               'auto_post_form': auto_post_form,
                               'is_valid': is_valid,
                               'status': status,
                               'message': message,
                               'allow_edit': allow_edit,
                              },
                              context_instance=RequestContext(request))


def draft_cancel(request, submission_id):
    detail = get_object_or_404(IdSubmissionDetail, submission_id=submission_id)
    detail.status_id = CANCELED
    detail.save()
    return HttpResponseRedirect(reverse(draft_status, None, kwargs={'submission_id': submission_id}))


def draft_edit(request, submission_id):
    detail = get_object_or_404(IdSubmissionDetail, submission_id=submission_id)
    if detail.status_id != UPLOADED:
        raise Http404
    validation = DraftValidation(detail)
    if request.method=='POST':
        form = MetaDataForm(draft=detail, validation=validation, data=request.POST)
        if form.is_valid():
            form.save(request)
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
        message = ('success', 'Authorization key accepted. Auto-Post complete')
        perform_post(detail)
    return draft_status(request, submission_id, message)


def draft_approve(request, submission_id):
    detail = get_object_or_404(IdSubmissionDetail, submission_id=submission_id)
    if detail.status_id == INITIAL_VERSION_APPROVAL_REQUESTED:
        validation = DraftValidation(detail)
        approved_detail = IdApprovedDetail()
        perform_post(detail)
    return HttpResponseRedirect(reverse(draft_status, None, kwargs={'submission_id': submission_id}))
