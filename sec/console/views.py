from django.http import HttpResponseRedirect, HttpResponse, HttpResponseForbidden
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext

from ietf.doc.models import *

def main(request):
    '''
    Main view for the Console
    '''

    latest_docevent = DocEvent.objects.all().order_by('-time')[0]
    
    return render_to_response('console/main.html', {
        'latest_docevent': latest_docevent},
        RequestContext(request, {}),
    )