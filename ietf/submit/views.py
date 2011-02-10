# Copyright The IETF Trust 2007, All Rights Reserved
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import get_object_or_404
from django.shortcuts import render_to_response
from django.template import RequestContext

from ietf.submit.models import IdSubmissionDetail
from ietf.submit.forms import UploadForm, AutoPostForm, MetaDataForm
from ietf.submit.utils import (DraftValidation, UPLOADED, WAITING_AUTHENTICATION,
                               perform_post)


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
        status = detail.status
        allow_edit = None
    if request.method=='POST' and allow_edit:
        if request.POST.get('autopost', False):
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
                               'allow_edit': allow_edit,
                               'message': message,
                              },
                              context_instance=RequestContext(request))


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
