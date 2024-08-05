# Copyright The IETF Trust 2007-2022, All Rights Reserved
# -*- coding: utf-8 -*-
#
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


import datetime
import importlib

# needed if we revert to higher barrier for account creation
#from datetime import datetime as DateTime, timedelta as TimeDelta, date as Date
from collections import defaultdict

import django.core.signing
from django import forms
from django.contrib import messages
from django.conf import settings
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.hashers import identify_hasher
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.contrib.sites.models import Site
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import IntegrityError
from django.urls import reverse as urlreverse
from django.http import Http404, HttpResponseRedirect, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.encoding import force_bytes

import debug                            # pyflakes:ignore

from ietf.group.models import Role, Group
from ietf.ietfauth.forms import ( RegistrationForm, PasswordForm, ResetPasswordForm, TestEmailForm,
                                ChangePasswordForm, get_person_form, RoleEmailForm,
                                NewEmailForm, ChangeUsernameForm, PersonPasswordForm)
from ietf.ietfauth.utils import has_role
from ietf.name.models import ExtResourceName
from ietf.nomcom.models import NomCom
from ietf.person.models import Person, Email, Alias, PersonalApiKey, PERSON_API_KEY_VALUES
from ietf.review.models import ReviewerSettings, ReviewWish, ReviewAssignment
from ietf.review.utils import unavailable_periods_to_list, get_default_filter_re
from ietf.doc.fields import SearchableDocumentField
from ietf.utils.decorators import person_required
from ietf.utils.mail import send_mail
from ietf.utils.validators import validate_external_resource_value
from ietf.utils.timezone import date_today, DEADLINE_TZINFO

# These are needed if we revert to the higher bar for account creation



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
#     if not request.user.is_authenticated:
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
    new_account_email = None

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            new_account_email = form.cleaned_data[
                "email"
            ]  # This will be lowercase if form.is_valid()
            email_is_known = False  # do we already know of the new_account_email address?

            # Find an existing Person to contact, if one exists
            person_to_contact = None
            user = User.objects.filter(username__iexact=new_account_email).first()
            if user is not None:
                email_is_known = True
                try:
                    person_to_contact = user.person
                except User.person.RelatedObjectDoesNotExist:
                    # User.person is a OneToOneField so it raises an exception if the field is null
                    pass  # leave person_to_contact as None
            if person_to_contact is None:
                email = Email.objects.filter(address__iexact=new_account_email).first()
                if email is not None:
                    email_is_known = True
                    # Email.person is a ForeignKey, so its value is None if the field is null
                    person_to_contact = email.person
            # Get a "good" email to contact the existing Person
            to_email = person_to_contact.email_address() if person_to_contact else None

            if to_email:
                # We have a "good" email - send instructions to it
                send_account_creation_exists_email(request, new_account_email, to_email)
            elif email_is_known:
                # Either a User or an Email matching new_account_email is in the system but we do not have a
                # "good" email to use to contact its owner. Fail so the user can contact the secretariat to sort
                # things out.
                form.add_error(
                    "email",
                    ValidationError(
                        f"Unable to create account for {new_account_email}. Please contact "
                        f"the Secretariat at {settings.SECRETARIAT_SUPPORT_EMAIL} for assistance."
                    ),
                )
                new_account_email = None  # Indicate to the template that we failed to create the requested account
            else:
                send_account_creation_email(request, new_account_email)

    else:
        form = RegistrationForm()

    return render(
        request,
        "registration/create.html",
        {
            "form": form,
            "to_email": new_account_email,
        },
    )


def send_account_creation_email(request, to_email):
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


def send_account_creation_exists_email(request, new_account_email, to_email):
    domain = Site.objects.get_current().domain
    subject = "Attempted account creation at %s" % domain
    from_email = settings.DEFAULT_FROM_EMAIL
    send_mail(
        request,
        to_email,
        from_email,
        subject,
        "registration/creation_exists_email.txt",
        {
            "domain": domain,
            "username": new_account_email,
        },
    )


def confirm_account(request, auth):
    try:
        email = django.core.signing.loads(auth, salt="create_account", max_age=settings.DAYS_TO_EXPIRE_REGISTRATION_LINK * 24 * 60 * 60)
    except django.core.signing.BadSignature:
        raise Http404("Invalid or expired auth")

    if User.objects.filter(username__iexact=email).exists():
        return redirect(profile)

    success = False
    if request.method == 'POST':
        form = PersonPasswordForm(request.POST)
        if form.is_valid():
            password = form.cleaned_data["password"]

            user = User.objects.create(username=email, email=email)
            user.set_password(password)
            user.save()

            # make sure the rest of the person infrastructure is
            # well-connected
            email_obj = Email.objects.filter(address=email).first()

            person = None
            if email_obj and email_obj.person:
                person = email_obj.person

            if not person:
                name = form.cleaned_data["name"]
                ascii = form.cleaned_data["ascii"]
                person = Person.objects.create(user=user,
                                               name=name,
                                               ascii=ascii)

                for name in set([ person.name, person.ascii, person.plain_name(), person.plain_ascii(), ]):
                    Alias.objects.create(person=person, name=name)

            if not email_obj:
                email_obj = Email.objects.create(address=email, person=person, origin=user.username)
            else:
                if not email_obj.person:
                    email_obj.person = person
                    email_obj.save()

            person.user = user
            person.save()

            success = True
    else:
        form = PersonPasswordForm()

    return render(request, 'registration/confirm_account.html', {
        'form': form,
        'email': email,
        'success': success,
    })

@login_required
@person_required
def profile(request):
    roles = []
    person = request.user.person

    roles = Role.objects.filter(person=person, group__state='active').order_by('name__name', 'group__name')
    emails = Email.objects.filter(person=person).exclude(address__startswith='unknown-email-').order_by('-active','-time')
    new_email_forms = []

    nc = NomCom.objects.filter(group__acronym__icontains=date_today().year).first()
    if nc and nc.volunteer_set.filter(person=person).exists():
        volunteer_status = 'volunteered'
    elif nc and nc.is_accepting_volunteers:
        volunteer_status = 'allow'
    else:
        volunteer_status = 'deny'

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
                from_email = settings.DEFAULT_FROM_EMAIL

                existing = Email.objects.filter(address=to_email).first()
                if existing:
                    subject = 'Attempt to add your email address by %s' % person.name
                    send_mail(request, to_email, from_email, subject, 'registration/add_email_exists_email.txt', {
                        'domain': domain,
                        'email': to_email,
                        'person': person,
                    })
                else:
                    subject = 'Confirm email address for %s' % person.name
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

            primary_email = request.POST.get("primary_email", None)
            active_emails = request.POST.getlist("active_emails", [])
            for email in emails:
                email.active = email.pk in active_emails
                email.primary = email.address == primary_email
                if email.primary and not email.active:
                    email.active = True
                if not email.origin:
                    email.origin = person.user.username
                email.save()

            # Make sure the alias table contains any new and/or old names.
            existing_aliases = set(Alias.objects.filter(person=person).values_list("name", flat=True))
            curr_names = set(x for x in [updated_person.name, updated_person.ascii, updated_person.ascii_short, updated_person.plain_name(), updated_person.plain_ascii(), ] if x)
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
        'person': person,
        'person_form': person_form,
        'roles': roles,
        'emails': emails,
        'new_email_forms': new_email_forms,
        'nomcom': nc,
        'volunteer_status': volunteer_status,
        'settings':settings,
    })

@login_required
@person_required
def edit_person_externalresources(request):
    class PersonExtResourceForm(forms.Form):
        resources = forms.CharField(widget=forms.Textarea, label="Additional Resources", required=False,
            help_text=("Format: 'tag value (Optional description)'."
                " Separate multiple entries with newline. When the value is a URL, use https:// where possible.") )

        def clean_resources(self):
            lines = [x.strip() for x in self.cleaned_data["resources"].splitlines() if x.strip()]
            errors = []
            for l in lines:
                parts = l.split()
                if len(parts) == 1:
                    errors.append("Too few fields: Expected at least tag and value: '%s'" % l)
                elif len(parts) >= 2:
                    name_slug = parts[0]
                    try:
                        name = ExtResourceName.objects.get(slug=name_slug)
                    except ObjectDoesNotExist:
                        errors.append("Bad tag in '%s': Expected one of %s" % (l, ', '.join([ o.slug for o in ExtResourceName.objects.all() ])))
                        continue
                    value = parts[1]
                    try:
                        validate_external_resource_value(name, value)
                    except ValidationError as e:
                        e.message += " : " + value
                        errors.append(e)
            if errors:
                raise ValidationError(errors)
            return lines

    def format_resources(resources, fs="\n"):
        res = []
        for r in resources:
            if r.display_name:
                res.append("%s %s (%s)" % (r.name.slug, r.value, r.display_name.strip('()')))
            else:
                res.append("%s %s" % (r.name.slug, r.value)) 
                # TODO: This is likely problematic if value has spaces. How then to delineate value and display_name? Perhaps in the short term move to comma or pipe separation.
                # Might be better to shift to a formset instead of parsing these lines.
        return fs.join(res)

    person = request.user.person

    old_resources = format_resources(person.personextresource_set.all())

    if request.method == 'POST':
        form = PersonExtResourceForm(request.POST)
        if form.is_valid():
            old_resources = sorted(old_resources.splitlines())
            new_resources = sorted(form.cleaned_data['resources'])
            if old_resources != new_resources:
                person.personextresource_set.all().delete()
                for u in new_resources:
                    parts = u.split(None, 2)
                    name = parts[0]
                    value = parts[1]
                    display_name = ' '.join(parts[2:]).strip('()')
                    person.personextresource_set.create(value=value, name_id=name, display_name=display_name)
                new_resources = format_resources(person.personextresource_set.all())
                messages.success(request,"Person resources updated.")
            else:
                messages.info(request,"No change in Person resources.")
            return redirect('ietf.ietfauth.views.profile')
    else:
        form = PersonExtResourceForm(initial={'resources': old_resources, })

    info = "Valid tags:<br><br> %s" % ', '.join([ o.slug for o in ExtResourceName.objects.all().order_by('slug') ])
    # May need to explain the tags more - probably more reason to move to a formset.
    title = "Additional person resources"
    return render(request, 'ietfauth/edit_field.html',dict(person=person, form=form, title=title, info=info) )

def confirm_new_email(request, auth):
    try:
        username, email = django.core.signing.loads(auth, salt="add_email", max_age=settings.DAYS_TO_EXPIRE_REGISTRATION_LINK * 24 * 60 * 60)
    except django.core.signing.BadSignature:
        raise Http404("Invalid or expired auth")

    person = get_object_or_404(Person, user__username__iexact=username)

    # do another round of validation since the situation may have
    # changed since submitting the request
    form = NewEmailForm({ "new_email": email })
    can_confirm = form.is_valid() and email
    new_email_obj = None
    created = False
    if request.method == 'POST' and can_confirm and request.POST.get("action") == "confirm":
        try: 
            new_email_obj, created = Email.objects.get_or_create(
                address=email, 
                person=person, 
                defaults={'origin': username},
            )
        except IntegrityError:
            can_confirm = False
            form.add_error(
                None, "Email address is in use by another user. Please contact the secretariat for assistance."
            )

    return render(request, 'registration/confirm_new_email.html', {
        'username': username,
        'email': email,
        'can_confirm': can_confirm,
        'form': form,
        'new_email_obj': new_email_obj,
        'already_confirmed': new_email_obj and not created,
    })

def password_reset(request):
    success = False
    if request.method == 'POST':
        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            submitted_username = form.cleaned_data['username']
            # The form validation checks that a matching User exists. Add the person__isnull check
            # because the OneToOne field does not gracefully handle checks for user.person is Null.
            # If we don't get a User here, we know it's because there's no related Person.
            # We still report that the action succeeded, so we're not leaking the existence of user
            # email addresses.
            user = User.objects.filter(username__iexact=submitted_username, person__isnull=False).first()
            if not user:
                # try to find user ID from the email address
                email = Email.objects.filter(address=submitted_username).first()
                if email and email.person:
                    if email.person.user:
                        user = email.person.user
                    else: 
                        # Create a User record with this (conditioned by way of Email) username
                        # Don't bother setting the name or email fields on User - rely on the
                        # Person pointer.
                        user = User.objects.create(
                            username=email.address.lower(), 
                            is_active=True,
                        )
                        email.person.user = user
                        email.person.save()
            if user and user.person.email_set.filter(active=True).exists():
                data = {
                    'username': user.username,
                    'password': user.password and user.password[-4:],
                    'last_login': user.last_login.timestamp() if user.last_login else None,
                }
                auth = django.core.signing.dumps(data, salt="password_reset")

                domain = Site.objects.get_current().domain
                subject = 'Confirm password reset at %s' % domain
                from_email = settings.DEFAULT_FROM_EMAIL
                # Send email to addresses from the database, NOT to the address from the form.
                # This prevents unicode spoofing tricks (https://nvd.nist.gov/vuln/detail/CVE-2019-19844).
                to_emails = list(set(email.address for email in user.person.email_set.filter(active=True)))
                to_emails.sort()
                send_mail(request, to_emails, from_email, subject, 'registration/password_reset_email.txt', {
                    'domain': domain,
                    'auth': auth,
                    'username': submitted_username,
                    'expire': settings.MINUTES_TO_EXPIRE_RESET_PASSWORD_LINK,
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
        data = django.core.signing.loads(auth, salt="password_reset", max_age=settings.MINUTES_TO_EXPIRE_RESET_PASSWORD_LINK * 60)
        username = data['username']
        password = data['password']
        last_login = None
        if data['last_login']:
            last_login = datetime.datetime.fromtimestamp(data['last_login'], datetime.timezone.utc)
    except django.core.signing.BadSignature:
        raise Http404("Invalid or expired auth")

    user = get_object_or_404(User, username__iexact=username, password__endswith=password, last_login=last_login)
    if request.user.is_authenticated and request.user != user:
        return HttpResponseForbidden(
            f'This password reset link is not for the signed-in user. '
            f'Please <a href="{urlreverse("django.contrib.auth.views.logout")}">sign out</a> and try again.'
        )
    success = False
    if request.method == 'POST':
        form = PasswordForm(request.POST)
        if form.is_valid():
            password = form.cleaned_data["password"]

            user.set_password(password)
            user.save()

            success = True
    else:
        form = PasswordForm()

    hlibname, hashername = settings.PASSWORD_HASHERS[0].rsplit('.',1)
    hlib = importlib.import_module(hlibname)
    hasher = getattr(hlib, hashername)
    return render(request, 'registration/change_password.html', {
        'form': form,
        'update_user': user,
        'success': success,
        'hasher': hasher,
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



class AddReviewWishForm(forms.Form):
    doc = SearchableDocumentField(label="Document", doc_type="draft")
    team = forms.ModelChoiceField(queryset=Group.objects.all(), empty_label="(Choose review team)")

    def __init__(self, teams, *args, **kwargs):
        super(AddReviewWishForm, self).__init__(*args, **kwargs)

        f = self.fields["team"]
        f.queryset = teams
        if len(f.queryset) == 1:
            f.initial = f.queryset[0].pk
            f.widget = forms.HiddenInput()

@login_required
def review_overview(request):
    open_review_assignments = ReviewAssignment.objects.filter(
        reviewer__person__user=request.user,
        state__in=["assigned", "accepted"],
    )
    today = date_today(DEADLINE_TZINFO)
    for r in open_review_assignments:
        r.due = max(0, (today - r.review_request.deadline).days)

    closed_review_assignments = ReviewAssignment.objects.filter(
        reviewer__person__user=request.user,
        state__in=["no-response", "part-completed", "completed"],
    ).order_by("-review_request__time")[:20]

    teams = Group.objects.filter(role__name="reviewer", role__person__user=request.user, state="active")

    settings = { o.team_id: o for o in ReviewerSettings.objects.filter(person__user=request.user, team__in=teams) }

    unavailable_periods = defaultdict(list)
    for o in unavailable_periods_to_list().filter(person__user=request.user, team__in=teams):
        unavailable_periods[o.team_id].append(o)

    roles = { o.group_id: o for o in Role.objects.filter(name="reviewer", person__user=request.user, group__in=teams) }

    for t in teams:
        t.reviewer_settings = settings.get(t.pk) or ReviewerSettings(team=t,filter_re = get_default_filter_re(request.user.person))
        t.unavailable_periods = unavailable_periods.get(t.pk, [])
        t.role = roles.get(t.pk)

    if request.method == "POST" and request.POST.get("action") == "add_wish":
        review_wish_form = AddReviewWishForm(teams, request.POST)
        if review_wish_form.is_valid():
            ReviewWish.objects.get_or_create(
                person=request.user.person,
                doc=review_wish_form.cleaned_data["doc"],
                team=review_wish_form.cleaned_data["team"],
            )

            return redirect(review_overview)
    else:
        review_wish_form = AddReviewWishForm(teams)

    if request.method == "POST" and request.POST.get("action") == "delete_wish":
        wish_id = request.POST.get("wish_id")
        if wish_id is not None:
            ReviewWish.objects.filter(pk=wish_id, person=request.user.person).delete()
        return redirect(review_overview)

    review_wishes = ReviewWish.objects.filter(person__user=request.user).prefetch_related("team")

    return render(request, 'ietfauth/review_overview.html', {
        'open_review_assignments': open_review_assignments,
        'closed_review_assignments': closed_review_assignments,
        'teams': teams,
        'review_wishes': review_wishes,
        'review_wish_form': review_wish_form,
    })

@login_required
def change_password(request):
    success = False
    person = None

    try:
        person = request.user.person
    except Person.DoesNotExist:
        return render(request, 'registration/missing_person.html')

    emails = [ e.address for e in Email.objects.filter(person=person, active=True).order_by('-primary','-time') ]
    user = request.user

    if request.method == 'POST':
        form = ChangePasswordForm(user, request.POST)
        if form.is_valid():
            new_password = form.cleaned_data["new_password"]
            
            user.set_password(new_password)
            user.save()
            # keep the session
            update_session_auth_hash(request, user)

            send_mail(request, emails, None, "Datatracker password change notification",
                "registration/password_change_email.txt", {'action_email': settings.SECRETARIAT_ACTION_EMAIL, })

            messages.success(request, "Your password was successfully changed")
            return HttpResponseRedirect(urlreverse('ietf.ietfauth.views.profile'))

    else:
        form = ChangePasswordForm(request.user)

    hlibname, hashername = settings.PASSWORD_HASHERS[0].rsplit('.',1)
    hlib = importlib.import_module(hlibname)
    hasher = getattr(hlib, hashername)
    return render(request, 'registration/change_password.html', {
        'form': form,
        'success': success,
        'hasher': hasher,
    })

    
@login_required
@person_required
def change_username(request):
    person = request.user.person

    emails = [ e.address for e in Email.objects.filter(person=person, active=True) ]
    emailz = [ e.address for e in person.email_set.filter(active=True) ]
    assert emails == emailz
    user = request.user

    if request.method == 'POST':
        form = ChangeUsernameForm(user, request.POST)
        if form.is_valid():
            new_username = form.cleaned_data["username"]
            assert new_username in emails

            user.username = new_username.lower()
            user.save()
            # keep the session
            update_session_auth_hash(request, user)

            send_mail(request, emails, None, "Datatracker username change notification", "registration/username_change_email.txt", {})

            messages.success(request, "Your username was successfully changed")
            return HttpResponseRedirect(urlreverse('ietf.ietfauth.views.profile'))

    else:
        form = ChangeUsernameForm(request.user)

    return render(request, 'registration/change_username.html', {'form': form})


class AnyEmailAuthenticationForm(AuthenticationForm):
    """AuthenticationForm that allows any email address as the username
    
    Also performs a check for a cleared password field and provides a helpful error message
    if that applies to the user attempting to log in.
    """
    _unauthenticated_user = None

    def clean_username(self):
        username = self.cleaned_data.get("username", None)
        if username is None:
            raise self.get_invalid_login_error()
        user = User.objects.filter(username__iexact=username).first()
        if user is None:
            email = Email.objects.filter(address=username).first()
            if email and email.person:
                user = email.person.user  # might be None
        if user is None:
            raise self.get_invalid_login_error()
        self._unauthenticated_user = user  # remember this for the clean() method
        return user.username

    def clean(self):
        if self._unauthenticated_user is not None:
            try: 
                identify_hasher(self._unauthenticated_user.password)
            except ValueError:
                self.add_error(
                    "password",
                    'Your password has been cleared because of possible password leakage. '
                    'Please use the "Forgot your password?" button below to set a new password '
                    'for your account.',
                )
        return super().clean()


class AnyEmailLoginView(LoginView):
    """LoginView that allows any email address as the username
    
    Redirects to the missing_person page instead of logging in if the user does not have a Person 
    """
    form_class = AnyEmailAuthenticationForm

    def form_valid(self, form):
        """Security check complete. Log the user in if they have a Person."""
        user = form.get_user()  # user has authenticated at this point
        if not hasattr(user, "person"):
            logout(self.request)  # should not be logged in yet, but just in case...
            return render(self.request, "registration/missing_person.html")
        return super().form_valid(form)
        

@login_required
@person_required
def apikey_index(request):
    person = request.user.person
    return render(request, 'ietfauth/apikeys.html', {'person': person})                

@login_required
@person_required
def apikey_create(request):
    endpoints = [('', '----------')] + list(set([ (v, n) for (v, n, r) in PERSON_API_KEY_VALUES if r==None or has_role(request.user, r) ]))
    class ApiKeyForm(forms.ModelForm):
        endpoint = forms.ChoiceField(choices=endpoints)

        class Meta:
            model = PersonalApiKey
            fields = ['endpoint']
    #
    person = request.user.person
    if request.method == 'POST':
        form = ApiKeyForm(request.POST)
        if form.is_valid():
            api_key = form.save(commit=False)
            api_key.person = person
            api_key.save()
            return redirect('ietf.ietfauth.views.apikey_index')
    else:
        form = ApiKeyForm()
    return render(request, 'form.html', {'form':form, 'title':"Create a new personal API key", 'description':'', 'button':'Create key'})


@login_required
@person_required
def apikey_disable(request):
    person = request.user.person
    choices = [ (k.hash(), str(k)) for k in person.apikeys.exclude(valid=False) ]
    #
    class KeyDeleteForm(forms.Form):
        hash = forms.ChoiceField(label='Key', choices=choices)
        def clean_hash(self):
            hash = force_bytes(self.cleaned_data['hash'])
            key = PersonalApiKey.validate_key(hash)
            if key and key.person == request.user.person:
                return hash
            else:
                raise ValidationError("Bad key value")
    #
    if request.method == 'POST':
        form = KeyDeleteForm(request.POST)
        if form.is_valid():
            hash = force_bytes(form.cleaned_data['hash'])
            key = PersonalApiKey.validate_key(hash)
            key.valid = False
            key.save()
            messages.success(request, "Disabled key %s" % hash)
            return redirect('ietf.ietfauth.views.apikey_index')
        else:
            messages.error(request, "Key validation failed; key not disabled")
    else:
        form = KeyDeleteForm(request.GET)
    return render(request, 'form.html', {'form':form, 'title':"Disable a personal API key", 'description':'', 'button':'Disable key'})
