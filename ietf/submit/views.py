# Copyright The IETF Trust 2007, All Rights Reserved
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.shortcuts import render_to_response
from django.template import RequestContext

from ietf.submit.models import IdSubmissionDetail
from ietf.submit.forms import UploadForm, AutoPostForm
from ietf.submit.utils import DraftValidation


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
    


def draft_status(request, submission_id):
    detail = get_object_or_404(IdSubmissionDetail, submission_id=submission_id)
    validation = DraftValidation(detail)
    is_valid = validation.is_valid()
    if request.method=='POST':
        if request.POST.get('autopost', False):
            auto_post_form = AutoPostForm(draft=detail, validation=validation, data=request.POST)
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
                              },
                              context_instance=RequestContext(request))


def draft_edit(request, submission_id):
    pass
