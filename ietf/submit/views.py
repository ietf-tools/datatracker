# Copyright The IETF Trust 2007, All Rights Reserved
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.shortcuts import render_to_response
from django.template import RequestContext

from ietf.submit.models import IdSubmissionDetail
from ietf.submit.forms import UploadForm
from ietf.submit.utils import check_idnits_success


def submit_index(request):
    if request.method == 'POST':
        form = UploadForm(data=request.POST, files=request.FILES)
        if form.is_valid():
            submit = form.save()
            return HttpResponseRedirect(reverse(draft_status, None, kwargs={'submission_id': submit.submission_id}))
    else:
        form = UploadForm()
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
    idnits_success = check_idnits_success(detail.idnits_message)
    return render_to_response('submit/draft_status.html', 
                              {'selected': 'status',
                               'detail': detail,
                               'idnits_success': idnits_success,
                              },
                              context_instance=RequestContext(request))
