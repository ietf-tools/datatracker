# Copyright The IETF Trust 2007, All Rights Reserved
import datetime
from email.utils import parseaddr

from django.conf import settings
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.forms.fields import email_re
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.utils import simplejson
from django.views.generic.list_detail import object_list, object_detail

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
