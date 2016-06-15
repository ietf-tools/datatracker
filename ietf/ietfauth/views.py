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

from datetime import datetime as DateTime, timedelta as TimeDelta

from django.conf import settings
from django.http import Http404  #, HttpResponse, HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
#from django.contrib.auth import REDIRECT_FIELD_NAME, authenticate, login
from django.contrib.auth.decorators import login_required
#from django.utils.http import urlquote
import django.core.signing
from django.contrib.sites.models import Site
from django.contrib.auth.models import User

import debug                            # pyflakes:ignore

from ietf.group.models import Role
from ietf.ietfauth.forms import RegistrationForm, PasswordForm, ResetPasswordForm, TestEmailForm, WhitelistForm
from ietf.ietfauth.forms import get_person_form, RoleEmailForm, NewEmailForm
from ietf.ietfauth.htpasswd import update_htpasswd_file
from ietf.ietfauth.utils import role_required
from ietf.mailinglists.models import Subscribed, Whitelisted
from ietf.person.models import Person, Email, Alias
from ietf.utils.mail import send_mail

def index(request):
    return render(request, 'registration/index.html')

# def url_login(request, user, passwd):
#     user = authenticate(username=user, password=passwd)
#     redirect_to = request.REQUEST.get(REDIRECT_FIELD_NAME, '')
#     if user is not None:
#         if user.is_active:
#             login(request, user)
#             return HttpResponseRedirect('/accounts/loggedin/?%s=%s' % (REDIRECT_FIELD_NAME, urlquote(redirect_to)))
#     return HttpResponse("Not authenticated?", status=500)

# @login_required
# def ietf_login(request):
#     if not request.user.is_authenticated():
#         return HttpResponse("Not authenticated?", status=500)
# 
#     redirect_to = request.REQUEST.get(REDIRECT_FIELD_NAME, '')
#     request.session.set_test_cookie()
#     return HttpResponseRedirect('/accounts/loggedin/?%s=%s' % (REDIRECT_FIELD_NAME, urlquote(redirect_to)))

# def ietf_loggedin(request):
#     if not request.session.test_cookie_worked():
#         return HttpResponse("You need to enable cookies")
#     request.session.delete_test_cookie()
#     redirect_to = request.REQUEST.get(REDIRECT_FIELD_NAME, '')
#     if not redirect_to or '//' in redirect_to or ' ' in redirect_to:
#         redirect_to = settings.LOGIN_REDIRECT_URL
#     return HttpResponseRedirect(redirect_to)

def create_account(request):
    to_email = None

    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            to_email = form.cleaned_data['email'] # This will be lowercase if form.is_valid()
            existing = Subscribed.objects.filter(email=to_email).first()
            ok_to_create = ( Whitelisted.objects.filter(email=to_email).exists()
                or existing and (existing.time + TimeDelta(seconds=settings.LIST_ACCOUNT_DELAY)) < DateTime.now() )
            if ok_to_create:
                auth = django.core.signing.dumps(to_email, salt="create_account")

                domain = Site.objects.get_current().domain
                subject = 'Confirm registration at %s' % domain
                from_email = settings.DEFAULT_FROM_EMAIL

                send_mail(request, to_email, from_email, subject, 'registration/creation_email.txt', {
                    'domain': domain,
                    'auth': auth,
                    'username': to_email,
                    'expire': settings.DAYS_TO_EXPIRE_REGISTRATION_LINK,
                })
            else:
                return render(request, 'registration/manual.html', { 'account_request_email': settings.ACCOUNT_REQUEST_EMAIL })
    else:
        form = RegistrationForm()

    return render(request, 'registration/create.html', {
        'form': form,
        'to_email': to_email,
    })

def confirm_account(request, auth):
    try:
        email = django.core.signing.loads(auth, salt="create_account", max_age=settings.DAYS_TO_EXPIRE_REGISTRATION_LINK * 24 * 60 * 60)
    except django.core.signing.BadSignature:
        raise Http404("Invalid or expired auth")

    if User.objects.filter(username=email).exists():
        return redirect(profile)

    success = False
    if request.method == 'POST':
        form = PasswordForm(request.POST)
        if form.is_valid():
            password = form.cleaned_data["password"]

            user = User.objects.create(username=email, email=email)
            user.set_password(password)
            user.save()
            # password is also stored in htpasswd file
            update_htpasswd_file(email, password)

            # make sure the rest of the person infrastructure is
            # well-connected
            email_obj = Email.objects.filter(address=email).first()

            person = None
            if email_obj and email_obj.person:
                person = email_obj.person

            if not person:
                person = Person.objects.create(user=user,
                                               name=email,
                                               ascii=email)
            if not email_obj:
                email_obj = Email.objects.create(address=email, person=person)
            else:
                if not email_obj.person:
                    email_obj.person = person
                    email_obj.save()

            person.user = user
            person.save()

            success = True
    else:
        form = PasswordForm()

    return render(request, 'registration/confirm_account.html', {
        'form': form,
        'email': email,
        'success': success,
    })

@login_required
def profile(request):
    roles = []
    person = None

    try:
        person = request.user.person
    except Person.DoesNotExist:
        return render(request, 'registration/missing_person.html')

    roles = Role.objects.filter(person=person, group__state='active').order_by('name__name', 'group__name')
    emails = Email.objects.filter(person=person).order_by('-active','-time')
    new_email_forms = []

    if request.method == 'POST':
        person_form = get_person_form(request.POST, instance=person)
        for r in roles:
            r.email_form = RoleEmailForm(r, request.POST, prefix="role_%s" % r.pk)

        for e in request.POST.getlist("new_email", []):
            new_email_forms.append(NewEmailForm({ "new_email": e }))

        forms_valid = [person_form.is_valid()] + [r.email_form.is_valid() for r in roles] + [f.is_valid() for f in new_email_forms]

        email_confirmations = []

        if all(forms_valid):
            updated_person = person_form.save()

            for f in new_email_forms:
                to_email = f.cleaned_data["new_email"]
                if not to_email:
                    continue

                email_confirmations.append(to_email)

                auth = django.core.signing.dumps([person.user.username, to_email], salt="add_email")

                domain = Site.objects.get_current().domain
                subject = u'Confirm email address for %s' % person.name
                from_email = settings.DEFAULT_FROM_EMAIL

                send_mail(request, to_email, from_email, subject, 'registration/add_email_email.txt', {
                    'domain': domain,
                    'auth': auth,
                    'email': to_email,
                    'person': person,
                    'expire': settings.DAYS_TO_EXPIRE_REGISTRATION_LINK,
                })
                

            for r in roles:
                e = r.email_form.cleaned_data["email"]
                if r.email_id != e.pk:
                    r.email = e
                    r.save()

            active_emails = request.POST.getlist("active_emails", [])
            for email in emails:
                email.active = email.pk in active_emails
                email.save()

            # Make sure the alias table contains any new and/or old names.
            existing_aliases = set(Alias.objects.filter(person=person).values_list("name", flat=True))
            curr_names = set(x for x in [updated_person.name, updated_person.ascii, updated_person.ascii_short, updated_person.plain_name(), ] if x)
            new_aliases = curr_names - existing_aliases
            for name in new_aliases:
                Alias.objects.create(person=updated_person, name=name)

            return render(request, 'registration/confirm_profile_update.html', {
                'email_confirmations': email_confirmations,
            })
    else:
        for r in roles:
            r.email_form = RoleEmailForm(r, prefix="role_%s" % r.pk)

        person_form = get_person_form(instance=person)

    return render(request, 'registration/edit_profile.html', {
        'user': request.user,
        'person': person,
        'person_form': person_form,
        'roles': roles,
        'emails': emails,
        'new_email_forms': new_email_forms,
    })

def confirm_new_email(request, auth):
    try:
        username, email = django.core.signing.loads(auth, salt="add_email", max_age=settings.DAYS_TO_EXPIRE_REGISTRATION_LINK * 24 * 60 * 60)
    except django.core.signing.BadSignature:
        raise Http404("Invalid or expired auth")

    person = get_object_or_404(Person, user__username=username)

    # do another round of validation since the situation may have
    # changed since submitting the request
    form = NewEmailForm({ "new_email": email })
    can_confirm = form.is_valid() and email
    new_email_obj = None
    if request.method == 'POST' and can_confirm and request.POST.get("action") == "confirm":
        new_email_obj = Email.objects.create(address=email, person=person)

    return render(request, 'registration/confirm_new_email.html', {
        'username': username,
        'email': email,
        'can_confirm': can_confirm,
        'form': form,
        'new_email_obj': new_email_obj,
    })

def password_reset(request):
    success = False
    if request.method == 'POST':
        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']

            auth = django.core.signing.dumps(username, salt="password_reset")

            domain = Site.objects.get_current().domain
            subject = 'Confirm password reset at %s' % domain
            from_email = settings.DEFAULT_FROM_EMAIL
            to_email = username # form validation makes sure that this is an email address

            send_mail(request, to_email, from_email, subject, 'registration/password_reset_email.txt', {
                'domain': domain,
                'auth': auth,
                'username': username,
                'expire': settings.DAYS_TO_EXPIRE_REGISTRATION_LINK,
            })

            success = True
    else:
        form = ResetPasswordForm()
    return render(request, 'registration/password_reset.html', {
        'form': form,
        'success': success,
    })


def confirm_password_reset(request, auth):
    try:
        username = django.core.signing.loads(auth, salt="password_reset", max_age=settings.DAYS_TO_EXPIRE_REGISTRATION_LINK * 24 * 60 * 60)
    except django.core.signing.BadSignature:
        raise Http404("Invalid or expired auth")

    user = get_object_or_404(User, username=username)

    success = False
    if request.method == 'POST':
        form = PasswordForm(request.POST)
        if form.is_valid():
            password = form.cleaned_data["password"]

            user.set_password(password)
            user.save()
            # password is also stored in htpasswd file
            update_htpasswd_file(user.username, password)

            success = True
    else:
        form = PasswordForm()

    return render(request, 'registration/change_password.html', {
        'form': form,
        'username': username,
        'success': success,
    })

def test_email(request):
    """Set email address to which email generated in the system will be sent."""
    if settings.SERVER_MODE == "production":
        raise Http404

    # Note that the cookie set here is only used when running in
    # "test" mode, normally you run the server in "development" mode,
    # in which case email is sent out as usual; for development, you
    # can easily start a little email debug server with Python, see
    # the instructions in utils/mail.py.

    cookie = None

    if request.method == "POST":
        form = TestEmailForm(request.POST)
        if form.is_valid():
            cookie = form.cleaned_data['email']
    else:
        form = TestEmailForm(initial=dict(email=request.COOKIES.get('testmailcc')))

    r = render(request, 'ietfauth/testemail.html', {
        "form": form,
        "cookie": cookie if cookie != None else request.COOKIES.get("testmailcc", "")
    })

    if cookie != None:
        r.set_cookie("testmailcc", cookie)

    return r

@role_required('Secretariat')
def add_account_whitelist(request):
    success = False
    if request.method == 'POST':
        form = WhitelistForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            entry = Whitelisted(email=email, by=request.user.person)
            entry.save()
            success = True
    else:
        form = WhitelistForm()

    return render(request, 'ietfauth/whitelist_form.html', {
        'form': form,
        'success': success,
    })

