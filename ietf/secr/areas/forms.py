from django import forms

from ietf.person.models import Person, Email

import re

STATE_CHOICES = (
    (1, 'Active'),
    (2, 'Concluded')
)


        
class AreaDirectorForm(forms.Form):
    ad_name = forms.CharField(max_length=100,label='Name',help_text="To see a list of people type the first name, or last name, or both.")
    #login = forms.EmailField(max_length=75,help_text="This should be the person's primary email address.")
    #email = forms.ChoiceField(help_text="This should be the person's primary email address.")
    email = forms.CharField(help_text="Select the email address to associate with this AD Role")
    
    # set css class=name-autocomplete for name field (to provide select list)
    def __init__(self, *args, **kwargs):
        super(AreaDirectorForm, self).__init__(*args, **kwargs)
        self.fields['ad_name'].widget.attrs['class'] = 'name-autocomplete'
        self.fields['email'].widget = forms.Select(choices=[])

    def clean_ad_name(self):
        name = self.cleaned_data.get('ad_name', '')
        # check for tag within parenthesis to ensure name was selected from the list 
        m = re.search(r'\((\d+)\)', name)
        if not name or not m:
            raise forms.ValidationError("You must select an entry from the list!")
        try:
            id = m.group(1)
            person = Person.objects.get(id=id)
        except Person.DoesNotExist:
            raise forms.ValidationError("ERROR finding Person with ID: %s" % id)
        return person

    def clean_email(self):
        # this ChoiceField gets populated by javascript so skip regular validation
        # which raises an error
        email = self.cleaned_data['email']
        if not email:
            raise forms.ValidationError("You must select an email.  If none are listed you'll need to add one first.")
        try:
            obj = Email.objects.get(address=email)
        except Email.DoesNotExist:
            raise forms.ValidationError("Can't find this email.")
        return obj
