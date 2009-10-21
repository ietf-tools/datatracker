# Copyright The IETF Trust 2007, All Rights Reserved

from django.template import RequestContext
from django.shortcuts import render_to_response
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist

@login_required
def my(request, addr=None):
    try:
	profile = request.user.get_profile()
	person = profile.person
    except ObjectDoesNotExist:
	person = None
    return render_to_response('registration/my.html', {
	'me': person,
	}, context_instance=RequestContext(request))
