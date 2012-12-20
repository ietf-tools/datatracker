# Portions Copyright (C) 2009 Nokia Corporation and/or its subsidiary(-ies).
# All rights reserved. Contact: Pasi Eronen <pasi.eronen@nokia.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#
#  * Neither the name of the Nokia Corporation and/or its
#    subsidiary(-ies) nor the names of its contributors may be used
#    to endorse or promote products derived from this software
#    without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# Copyright The IETF Trust 2007, All Rights Reserved

import datetime
import hashlib

from django.conf import settings
from django.template import RequestContext
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.contrib.auth import REDIRECT_FIELD_NAME, authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.utils.http import urlquote
from django.utils import simplejson as json
from django.utils.translation import ugettext as _

from ietf.ietfauth.forms import RegistrationForm, PasswordForm, RecoverPasswordForm, TestEmailForm

def index(request):
    return render_to_response('registration/index.html', context_instance=RequestContext(request))

def url_login(request, user, passwd):
    user = authenticate(username=user, password=passwd)
    redirect_to = request.REQUEST.get(REDIRECT_FIELD_NAME, '')
    if user is not None:
        if user.is_active:
            login(request, user)
            return HttpResponseRedirect('/accounts/loggedin/?%s=%s' % (REDIRECT_FIELD_NAME, urlquote(redirect_to)))
    return HttpResponse("Not authenticated?", status=500)

def ietf_login(request):
    if not request.user.is_authenticated():
        # This probably means an exception occured inside IetfUserBackend
        return HttpResponse("Not authenticated?", status=500)
    redirect_to = request.REQUEST.get(REDIRECT_FIELD_NAME, '')
    request.session.set_test_cookie()
    return HttpResponseRedirect('/accounts/loggedin/?%s=%s' % (REDIRECT_FIELD_NAME, urlquote(redirect_to)))

def ietf_loggedin(request):
    if not request.session.test_cookie_worked():
        return HttpResponse("You need to enable cookies")
    request.session.delete_test_cookie()
    redirect_to = request.REQUEST.get(REDIRECT_FIELD_NAME, '')
    if not redirect_to or '//' in redirect_to or ' ' in redirect_to:
        redirect_to = settings.LOGIN_REDIRECT_URL
    return HttpResponseRedirect(redirect_to)

@login_required
def profile(request):
    from ietf.person.models import Person, Email, Alias
    from ietf.group.models import Role
    from ietf.ietfauth.forms import PersonForm

    roles = []
    person = None
    try:
        person = request.user.get_profile()
    except Person.DoesNotExist:
        pass

    if request.method == 'POST':
        form = PersonForm(request.POST, instance=person)
        success = False
        new_emails = None
        error = None
        if form.is_valid():
            try:
                form.save()
                success = True
                new_emails = form.new_emails
            except Exception as e:
                error = e
            
        return render_to_response('registration/confirm_profile_update.html',
            { 'success': success, 'new_emails': new_emails, 'error': error} ,
                              context_instance=RequestContext(request))
    else:
        roles = Role.objects.filter(person=person,group__state='active').order_by('name__name','group__name')
        emails = Email.objects.filter(person=person).order_by('-active','-time')
        aliases = Alias.objects.filter(person=person)

        person_form = PersonForm(instance=person)

        return render_to_response('registration/edit_profile.html',
            { 'user': request.user, 'emails': emails, 'person': person, 
              'roles': roles, 'person_form': person_form } ,
                              context_instance=RequestContext(request))

def confirm_new_email(request, username, date, email, hash):
    from ietf.person.models import Person, Email, Alias
    from django.core.exceptions import ValidationError, NON_FIELD_ERRORS
    valid = hashlib.md5('%s%s%s%s' % (settings.SECRET_KEY, date, email, username)).hexdigest() == hash
    if not valid:
        raise Http404
    request_date = datetime.date(int(date[:4]), int(date[4:6]), int(date[6:]))
    if datetime.date.today() > (request_date + datetime.timedelta(days=settings.DAYS_TO_EXPIRE_REGISTRATION_LINK)):
        raise Http404
    success = False

    person = None
    error = None
    new_email = None

    try:
        # First, check whether this address exists (to give a more sensible
        # error when a duplicate is created).
        existing_email = Email.objects.get(address=email)
        print existing_email
        existing_person = existing_email.person 
        print existing_person
        error = {'address': ["Email address '%s' is already assigned to user '%s' (%s)" %
            (email, existing_person.user, existing_person.name)]}
    except Exception:
        try:
            person = Person.objects.get(user__username=username)
            new_email = Email(address=email, person=person, active=True, time=datetime.datetime.now())
            new_email.full_clean()
            new_email.save()
            success = True
        except Person.DoesNotExist:
            error = {'person': ["No such user: %s" % (username)]}
        except ValidationError as e:
            error = e.message_dict

    return render_to_response('registration/confirm_new_email.html',
                              { 'username': username, 'email': email,
                                'success': success, 'error': error,
                                'record': new_email},
                              context_instance=RequestContext(request))


def create_account(request):
    success = False
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.request = request
            form.save()
            success = True
    else:
        form = RegistrationForm()
    return render_to_response('registration/create.html',
                              {'form': form,
                               'success': success},
                              context_instance=RequestContext(request))


def process_confirmation(request, username, date, realm, hash):
    valid = hashlib.md5('%s%s%s%s' % (settings.SECRET_KEY, date, username, realm)).hexdigest() == hash
    if not valid:
        raise Http404
    request_date = datetime.date(int(date[:4]), int(date[4:6]), int(date[6:]))
    if datetime.date.today() > (request_date + datetime.timedelta(days=settings.DAYS_TO_EXPIRE_REGISTRATION_LINK)):
        raise Http404
    success = False
    if request.method == 'POST':
        form = PasswordForm(request.POST, username=username)
        if form.is_valid():
            form.save()                 # Also updates the httpd password file
            success = True
    else:
        form = PasswordForm(username=username)
    return form, username, success

def confirm_account(request, username, date, realm, hash):
    form, username, success = process_confirmation(request, username, date, realm, hash)
    return render_to_response('registration/confirm.html',
                              {'form': form, 'email': username, 'success': success},
                              context_instance=RequestContext(request))


def password_reset_view(request):
    success = False
    if request.method == 'POST':
        form = RecoverPasswordForm(request.POST)
        if form.is_valid():
            form.request = request
            form.save()
            success = True
    else:
        form = RecoverPasswordForm()
    return render_to_response('registration/password_reset.html',
                              {'form': form,
                               'success': success},
                              context_instance=RequestContext(request))


def confirm_password_reset(request, username, date, realm, hash):
    form, username, success = process_confirmation(request, username, date, realm, hash)
    return render_to_response('registration/change_password.html',
                              {'form': form,
                               'success': success,
                               'username': username},
                              context_instance=RequestContext(request))

def ajax_check_username(request):
    username = request.GET.get('username', '')
    error = False
    if User.objects.filter(username=username).count():
        error = _('This email address is already registered')
    return HttpResponse(json.dumps({'error': error}), mimetype='text/plain')
    
def test_email(request):
    if settings.SERVER_MODE == "production":
        raise Http404()

    # note that the cookie set here is only used when running in
    # "test" mode, normally you run the server in "development" mode,
    # in which case email is sent out as usual; for development, put
    # this
    #
    # EMAIL_HOST = 'localhost'
    # EMAIL_PORT = 1025
    # EMAIL_HOST_USER = None
    # EMAIL_HOST_PASSWORD = None
    # EMAIL_COPY_TO = ""
    #
    # in your settings.py and start a little debug email server in a
    # console with the following (it receives and prints messages)
    #
    # python -m smtpd -n -c DebuggingServer localhost:1025

    cookie = None

    if request.method == "POST":
        form = TestEmailForm(request.POST)
        if form.is_valid():
            cookie = form.cleaned_data['email']
    else:
        form = TestEmailForm(initial=dict(email=request.COOKIES.get('testmailcc')))

    r = render_to_response('ietfauth/testemail.html',
                           dict(form=form,
                                cookie=cookie if cookie != None else request.COOKIES.get("testmailcc", "")
                                ),
                           context_instance=RequestContext(request))

    if cookie != None:
        r.set_cookie("testmailcc", cookie)

    return r

