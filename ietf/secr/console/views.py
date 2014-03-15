
from django.shortcuts import render_to_response
from django.template import RequestContext

from ietf.doc.models import DocEvent

def main(request):
    '''
    Main view for the Console
    '''

    latest_docevent = DocEvent.objects.all().order_by('-time')[0]
    
    return render_to_response('console/main.html', {
        'latest_docevent': latest_docevent},
        RequestContext(request, {}),
    )
