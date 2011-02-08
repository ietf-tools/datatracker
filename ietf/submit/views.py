# Copyright The IETF Trust 2007, All Rights Reserved
from django.shortcuts import render_to_response
from django.template import RequestContext

from ietf.submit.forms import UploadForm


def submit_index(request):
    if request.method == 'POST':
        form = UploadForm(data=request.POST, files=request.FILES)
        if form.is_valid():
            pass
    else:
        form = UploadForm()
    return render_to_response('submit/submit_index.html', 
                              {'selected': 'index',
                               'form': form},
                              context_instance=RequestContext(request))


def submit_status(request):
    pass
