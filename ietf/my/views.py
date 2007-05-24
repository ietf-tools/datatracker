from django.http import HttpResponse,HttpResponseRedirect
from django import newforms as forms
from django.template import RequestContext
from django.shortcuts import render_to_response
from ietf.idtracker.models import PersonOrOrgInfo

def my(request, addr=None):
    if request.user:
	person = request.user.get_profile().person
    else:
	person = PersonOrOrgInfo.objects.distinct().get(emailaddresses__email_address=addr)
    return render_to_response('my/my.html', {
	'me': person,
	}, context_instance=RequestContext(request))
