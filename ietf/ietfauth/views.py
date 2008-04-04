# Copyright The IETF Trust 2007, All Rights Reserved
from django.conf import settings
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.http import HttpResponseRedirect
from django.contrib.sites.models import Site
from django.contrib.auth.models import User
from ietf.idtracker.models import PersonOrOrgInfo
from ietf.ietfauth.models import UserMap
from ietf.ietfauth.forms import EmailForm, ChallengeForm, PWForm, FirstLastForm, email_hash
from ietf.ietfauth.auth import set_password
from ietf.utils.mail import send_mail
from ietf.utils.users import create_user
from ietf.utils.log import log
import time

def password_request(request):
    if request.method == 'POST':
	form = EmailForm(request.POST)
	if form.is_valid():
	    timestamp = int(time.time())
	    email = form.clean_data['email']
	    hash = email_hash(email, timestamp)
	    site = Site.objects.get_current()
	    context = {'timestamp': timestamp, 'email': email, 'hash': hash, 'days': settings.PASSWORD_DAYS, 'site': site}
	    send_mail(request, email, None, 'IETF Datatracker Password',
			'registration/password_email.txt', context, toUser=True)
	    return render_to_response('registration/challenge_sent.html', context,
			context_instance=RequestContext(request))
    else:
	form = EmailForm()
    return render_to_response('registration/password_request.html', {'form': form},
		context_instance=RequestContext(request))

def password_return(request):
    form = ChallengeForm(request.REQUEST)
    if form.is_valid():
	email = form.clean_data['email']
	method = request.method
	try:
	    # Is there a django user?
	    user = User.objects.get(email__iexact=email)
	    try:
		usermap = UserMap.objects.get(user=user)
		person = usermap.person
	    except UserMap.DoesNotExist:
		person = None
	except User.DoesNotExist:
	    # Is there an IETF person, and a usermap to a django user,
	    # e.g., the django user table has the wrong email address?
	    user = None
	    try:
		person = PersonOrOrgInfo.objects.distinct().get(emailaddress__address__iexact=email)
		try:
		    usermap = UserMap.objects.get(person=person)
		    user = usermap.user
		except UserMap.DoesNotExist:
		    pass
	    except PersonOrOrgInfo.DoesNotExist:
		person = None
	if person is None:
	    # If there's no IETF person, try creating one.
	    if method == 'POST':
		flform = FirstLastForm(request.POST)
		if flform.is_valid():
		    person = PersonOrOrgInfo( first_name=flform.clean_data['first'], last_name=flform.clean_data['last'], created_by='SelfSvc' )
		    person.save()
		    person.emailaddress_set.create( type='INET', priority=1, address=email, comment='Created with SelfService' )
		    # fall through to "if user or person"
		    # hack:
		    # pretend to the fall-through form that we used GET.
		    method = 'GET'
	    else:
		flform = FirstLastForm()
		return render_to_response('registration/new_person_form.html', {'form': form, 'flform': flform},
			context_instance=RequestContext(request))
	if user or person:
	    # form to get a password, either for reset or new user
	    if method == 'POST':
		pwform = PWForm(request.POST)
		if pwform.is_valid():
		    pw = pwform.clean_data['password']
		    if user:
			set_password(user, pw)
			user.save()
			return HttpResponseRedirect('changed/')
		    else:
			create_user(None, email, person, pw=pw)
			return HttpResponseRedirect('created/')
	    else:
		pwform = PWForm()
	    return render_to_response('registration/password_form.html', {'u': user, 'person': person, 'form': form, 'pwform': pwform},
		    context_instance=RequestContext(request))
	else:
	    # We shouldn't get here.
	    return render_to_response('registration/generic_failure.html', {},
		    context_instance=RequestContext(request))
    else:
	log("bad challenge for %s: %s" % (form.data.get('email', '<None>'), form.errors.as_text().replace('\n', ' ').replace('   *', ':')))
	return render_to_response('registration/bad_challenge.html', {'form': form, 'days': settings.PASSWORD_DAYS},
		context_instance=RequestContext(request))
