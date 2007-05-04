from django.http import HttpResponse,HttpResponseRedirect
from django import newforms as forms
from django.template import RequestContext, Context, loader
from django.shortcuts import get_object_or_404
from ietf.idtracker.models import PersonOrOrgInfo, EmailAddress

def my(request, addr=None):
    if addr is None:
	# get email address from logged in user
        return 
    person = PersonOrOrgInfo.objects.filter(emailaddresses__email_address=addr).distinct()
    if len(person) != 1:
	if len(person) == 0:
	    raise Http404
	# multiple people matched!
	return "Oops"
    t = loader.get_template('my/my.html')
    c = RequestContext(request, {
	'me': person[0],
	})
    return HttpResponse(t.render(c))
