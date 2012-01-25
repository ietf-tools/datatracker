from django import forms
from django.core.validators import email_re

from ietf.person.models import Email, Person

import re


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

class PersonForm(forms.ModelForm):
    class Meta:
        model = Person
        exclude = ('time')

# ------------------------------------------------------
# Forms for addition of new contacts
# These sublcass the regular forms, with additional
# validations
# ------------------------------------------------------

class NewEmailForm(EmailForm):
    def clean_address(self):
        cleaned_data = self.cleaned_data
        address = cleaned_data.get("address")

        if address and not email_re.match(address):
            raise forms.ValidationError("Enter a valid email address")

        return address
        
class NewPersonForm(PersonForm):
    # use this method to set attrs which keeps other meta info from model.  
    def __init__(self, *args, **kwargs):
        super(NewPersonForm, self).__init__(*args, **kwargs)
        self.fields['name'].required=True

    def clean_name(self):
        # get name, strip leading and trailing spaces
        name = self.cleaned_data.get('name', '')
        # check for invalid characters
        r1 = re.compile(r'[a-zA-Z\-\.\(\) ]+$')
        if not r1.match(name):
            raise forms.ValidationError("Enter a valid name. (only letters,period,hyphen,paren allowed)") 
        return name

