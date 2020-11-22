# Copyright The IETF Trust 2011-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import re
from unidecode import unidecode

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User
from django.utils.html import mark_safe # type:ignore
from django.urls import reverse as urlreverse

from django_password_strength.widgets import PasswordStrengthInput, PasswordConfirmationInput

import debug                            # pyflakes:ignore

from ietf.person.models import Person, Email
from ietf.mailinglists.models import Whitelisted
from ietf.utils.text import isascii

class RegistrationForm(forms.Form):
    email = forms.EmailField(label="Your email (lowercase)")

    def clean_email(self):
        email = self.cleaned_data.get('email', '')
        if not email:
            return email
        if email.lower() != email:
            raise forms.ValidationError('The supplied address contained uppercase letters.  Please use a lowercase email address.')
        if User.objects.filter(username=email).exists():
            raise forms.ValidationError('An account with the email address you provided already exists.')
        return email


class PasswordForm(forms.Form):
    password = forms.CharField(widget=PasswordStrengthInput(attrs={'class':'password_strength'}))
    password_confirmation = forms.CharField(widget=PasswordConfirmationInput(
                                                        confirm_with='password',
                                                        attrs={'class':'password_confirmation'}),
                                            help_text="Enter the same password as above, for verification.",)
                                            

    def clean_password_confirmation(self):
        password = self.cleaned_data.get("password", "")
        password_confirmation = self.cleaned_data["password_confirmation"]
        if password != password_confirmation:
            raise forms.ValidationError("The two password fields didn't match.")
        return password_confirmation

def ascii_cleaner(supposedly_ascii):
    outside_printable_ascii_pattern = r'[^\x20-\x7F]'
    if re.search(outside_printable_ascii_pattern, supposedly_ascii):
        raise forms.ValidationError("Only unaccented Latin characters are allowed.")
    return supposedly_ascii

def prevent_at_symbol(name):
    if "@" in name:
        raise forms.ValidationError("Please fill in name - this looks like an email address (@ is not allowed in names).")

def prevent_system_name(name):
    name_without_spaces = name.replace(" ", "").replace("\t", "")
    if "(system)" in name_without_spaces.lower():
        raise forms.ValidationError("Please pick another name - this name is reserved.")

def prevent_anonymous_name(name):
    name_without_spaces = name.replace(" ", "").replace("\t", "")
    if "anonymous" in name_without_spaces.lower():
        raise forms.ValidationError("Please pick another name - this name is reserved.")

class PersonPasswordForm(forms.ModelForm, PasswordForm):

    class Meta:
        model = Person
        fields = ['name', 'ascii']

    def clean_name(self):
        name = self.cleaned_data.get('name', '')
        prevent_at_symbol(name)
        prevent_system_name(name)
        prevent_anonymous_name(name)

        return name

    def clean_ascii(self):
        ascii = self.cleaned_data.get('ascii', '')
        if not isascii(ascii):
            raise forms.ValidationError("Ascii name contains non-ASCII characters.")

        return ascii

def get_person_form(*args, **kwargs):

    exclude_list = ['time', 'user', 'photo_thumb', 'photo', ]

    person = kwargs['instance']
    roles = person.role_set.all()
    if not roles:
        exclude_list += ['biography', 'photo', ]

    class PersonForm(forms.ModelForm):
        class Meta:
            model = Person
            exclude = exclude_list
            widgets = {
                'consent': forms.widgets.CheckboxInput,
            }            

        def __init__(self, *args, **kwargs):
            super(PersonForm, self).__init__(*args, **kwargs)

            # blank ascii if it's the same as name
            self.fields["ascii"].required = self.fields["ascii"].widget.is_required = False
            self.fields["ascii"].help_text += " " + "Leave blank to use auto-reconstructed Latin version of name."

            if self.initial.get("ascii") == self.initial.get("name"):
                self.initial["ascii"] = ""

            for f in ['name', 'ascii', 'ascii_short', 'biography', 'photo', 'photo_thumb', ]:
                if f in self.fields:
                    self.fields[f].label += ' \u2020'

            self.unidecoded_ascii = False

            if self.data and not self.data.get("ascii", "").strip():
                self.data = self.data.copy()
                name = self.data["name"]
                reconstructed_name = unidecode(name)
                self.data["ascii"] = reconstructed_name
                self.unidecoded_ascii = name != reconstructed_name

        def clean_name(self):
            name = self.cleaned_data.get("name") or ""
            prevent_at_symbol(name)
            prevent_system_name(name)
            return name

        def clean_ascii(self):
            if self.unidecoded_ascii:
                raise forms.ValidationError("Name contained non-ASCII characters, and was automatically reconstructed using only Latin characters. Check the result - if you are happy, just hit Submit again.")

            name = self.cleaned_data.get("ascii") or ""
            prevent_at_symbol(name)
            prevent_system_name(name)
            return ascii_cleaner(name)

        def clean_ascii_short(self):
            name = self.cleaned_data.get("ascii_short") or ""
            prevent_at_symbol(name)
            prevent_system_name(name)
            return ascii_cleaner(name)

        def clean_consent(self):
            consent = self.cleaned_data.get('consent')
            require_consent = (
                self.cleaned_data.get('name') != person.name_from_draft
                or self.cleaned_data.get('ascii') != person.name_from_draft
                or self.cleaned_data.get('biography')
            )
            if consent == False and require_consent:
                raise forms.ValidationError("In order to modify your profile with data that require consent, you must permit the IETF to use the uploaded data.")
            return consent

    return PersonForm(*args, **kwargs)


class NewEmailForm(forms.Form):
    new_email = forms.EmailField(label="New email address", required=False)

    def clean_new_email(self):
        email = self.cleaned_data.get("new_email", "")
        if email:
            existing = Email.objects.filter(address=email).first()
            if existing:
                raise forms.ValidationError("Email address '%s' is already assigned to account '%s' (%s)" % (existing, existing.person and existing.person.user, existing.person))

        for pat in settings.EXCLUDED_PERSONAL_EMAIL_REGEX_PATTERNS:
            if re.search(pat, email):
                raise ValidationError("This email address is not valid in a datatracker account")

        return email


class RoleEmailForm(forms.Form):
    email = forms.ModelChoiceField(label="Role email", queryset=Email.objects.all())

    def __init__(self, role, *args, **kwargs):
        super(RoleEmailForm, self).__init__(*args, **kwargs)

        f = self.fields["email"]
        f.label = "%s in %s" % (role.name, role.group.acronym.upper())
        f.help_text = "Email to use for <i>%s</i> role in %s" % (role.name, role.group.name)
        f.queryset = f.queryset.filter(models.Q(person=role.person_id) | models.Q(role=role)).distinct()
        f.initial = role.email_id
        f.choices = [(e.pk, e.address if e.active else "({})".format(e.address)) for e in f.queryset]


class ResetPasswordForm(forms.Form):
    username = forms.EmailField(label="Your email (lowercase)")

    def clean_username(self):
        import ietf.ietfauth.views
        username = self.cleaned_data["username"]
        if not User.objects.filter(username=username).exists():
            raise forms.ValidationError(mark_safe("Didn't find a matching account. If you don't have an account yet, you can <a href=\"{}\">create one</a>.".format(urlreverse(ietf.ietfauth.views.create_account))))
        return username


class TestEmailForm(forms.Form):
    email = forms.EmailField(required=False)

class WhitelistForm(forms.ModelForm):
    class Meta:
        model = Whitelisted
        exclude = ['by', 'time' ]

    
from django import forms


class ChangePasswordForm(forms.Form):
    current_password = forms.CharField(widget=forms.PasswordInput)

    new_password = forms.CharField(widget=PasswordStrengthInput(attrs={'class':'password_strength'}))
    new_password_confirmation = forms.CharField(widget=PasswordConfirmationInput(
                                                    confirm_with='new_password',
                                                    attrs={'class':'password_confirmation'}))

    def __init__(self, user, data=None):
        self.user = user
        super(ChangePasswordForm, self).__init__(data)

    def clean_current_password(self):
        password = self.cleaned_data.get('current_password', None)
        if not self.user.check_password(password):
            raise ValidationError('Invalid password')
        return password
            
    def clean(self):
        new_password = self.cleaned_data.get('new_password', None)
        conf_password = self.cleaned_data.get('new_password_confirmation', None)
        if not new_password == conf_password:
            raise ValidationError("The password confirmation is different than the new password")


class ChangeUsernameForm(forms.Form):
    username = forms.ChoiceField(choices=[('-','--------')])
    password = forms.CharField(widget=forms.PasswordInput, help_text="Confirm the change with your password")

    def __init__(self, user, *args, **kwargs):
        assert isinstance(user, User)
        super(ChangeUsernameForm, self).__init__(*args, **kwargs)
        self.user = user
        emails = user.person.email_set.filter(active=True)
        choices = [ (email.address, email.address) for email in emails ]
        self.fields['username'] = forms.ChoiceField(choices=choices)

    def clean_password(self):
        password = self.cleaned_data['password']
        if not self.user.check_password(password):
            raise ValidationError('Invalid password')
        return password

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise ValidationError("A login with that username already exists.  Please contact the secretariat to get this resolved.")
        return username
