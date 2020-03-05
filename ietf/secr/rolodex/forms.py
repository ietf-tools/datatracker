# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import re

from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import validate_email, EmailValidator

import debug                            # pyflakes:ignore

from ietf.doc.models import Document
from ietf.group.models import Group
from ietf.name.models import RoleName
from ietf.person.models import Email, Person


class SearchForm(forms.Form):
    name = forms.CharField(max_length=50,required=False)
    email = forms.CharField(max_length=255,required=False)
    id = forms.IntegerField(required=False)

    def clean(self):
        super(SearchForm, self).clean()
        if any(self.errors):
            return
        data = self.cleaned_data
        if not data['name'] and not data['email'] and not data['id']:
            raise forms.ValidationError("You must fill out at least one field")
        
        return data

class EmailForm(forms.ModelForm):
    class Meta:
        model = Email
        fields = '__all__'
        widgets = {
            'address': forms.TextInput(attrs={'readonly':True}),
            'origin':  forms.TextInput(attrs={'blank':False}),
        }

    def clean_origin(self):
        validate_email = EmailValidator("Please provide the origin of the new email: A valid user email if provided by email, or 'author: doc' or 'role: role spec'.")
        if 'origin' in self.changed_data and self.instance.origin:
            raise forms.ValidationError("You may not change existing origin fields, only set the value when empty")
        origin = self.cleaned_data['origin']
        if ':' in origin:
            valid_tags = ['author', 'role', 'registration', ]
            tag, value = [ v.strip() for v in origin.split(':', 1) ]
            if not tag in valid_tags:
                raise forms.ValidationError("Invalid tag.  Valid tags are: %s" % ','.join(valid_tags))
            if   tag == 'author':
                if not Document.objects.filter(name=value).exists():
                    raise forms.ValidationError("Invalid document: %s. A valid document is required with 'author:'" % value)
            elif tag == 'role':
                if not ' ' in value:
                    raise forms.ValidationError("Invalid role spec: %s.  Please indicate 'group role'." % value)
                acronym, slug = value.split(None, 1)
                if not Group.objects.filter(acronym=acronym).exists():
                    raise forms.ValidationError("Invalid group: %s. A valid 'group role' string is required with 'role:'" % acronym)
                if not RoleName.objects.filter(slug=slug).exists():
                    roles = RoleName.objects.values_list('slug', flat=True)
                    raise forms.ValidationError("Invalid role: %s. A valid 'group role' string is required with 'role:'.\n  Valid roles are: %s" % (slug, ', '.join(roles)))
        else:
            validate_email(origin)
        return origin
                

class EditPersonForm(forms.ModelForm):
    class Meta:
        model = Person
        exclude = ('time',)

    def __init__(self, *args, **kwargs):
        super(EditPersonForm, self).__init__(*args,**kwargs)
        self.fields['user'] = forms.CharField(max_length=64,required=False,help_text="Corresponds to Django User ID (usually email address)")
        if self.instance.user:
            self.initial['user'] = self.instance.user.username
        
    def clean_user(self):
        user = self.cleaned_data['user']
        if user:
            # if Django User object exists return it, otherwise create one
            try:
                user_obj = User.objects.get(username=user)
            except User.DoesNotExist:
                user_obj = User.objects.create_user(user,user)
                
            return user_obj
        else:
            return None
        
# ------------------------------------------------------
# Forms for addition of new contacts
# These sublcass the regular forms, with additional
# validations
# ------------------------------------------------------

class NameForm(forms.Form):
    name = forms.CharField(max_length=255)

    def clean_name(self):
        # get name, strip leading and trailing spaces
        name = self.cleaned_data.get('name', '')
        # check for invalid characters
        r1 = re.compile(r'[a-zA-Z23\-\.\(\) ]+$')
        if not r1.match(name):
            raise forms.ValidationError("Enter a valid name. (only letters,period,hyphen,paren,numerals 2 and 3 allowed)") 
        return name
        
class NewEmailForm(EmailForm):
    def clean_address(self):
        cleaned_data = self.cleaned_data
        address = cleaned_data.get("address")

        if address:
            validate_email(address)

            for pat in settings.EXCLUDED_PERSONAL_EMAIL_REGEX_PATTERNS:
                if re.search(pat, address):
                    raise ValidationError("This email address is not valid in a datatracker account")

        return address
        
class NewPersonForm(forms.ModelForm):
    email = forms.EmailField()
    
    class Meta:
        model = Person
        exclude = ('time','user')

    def clean_email(self):
        email = self.cleaned_data['email']
        
        # error if there is already an account (User, Person) associated with this email
        try:
            user = User.objects.get(username=email)
            person = Person.objects.get(user=user)
            if user and person:
                raise forms.ValidationError("This account already exists. [name=%s, id=%s, email=%s]" % (person.name,person.id,email))
        except ObjectDoesNotExist:
            pass
            
        # error if email already exists
        if Email.objects.filter(address=email,active=True):
            raise forms.ValidationError("This email address already exists in the database")
        
        return email



