from django import forms
from sec.areas.models import *
import re

class LiaisonForm(forms.Form):
    liaison_name = forms.CharField(max_length=100,label='Name',help_text="To see a list of people type the first name, or last name, or both.")
    affiliation = forms.CharField(max_length=50)

    # set css class=name-autocomplete for name field (to provide select list)
    def __init__(self, *args, **kwargs):
        super(LiaisonForm, self).__init__(*args, **kwargs)
        self.fields['liaison_name'].widget.attrs['class'] = 'name-autocomplete'

    def clean_liaison_name(self):
        name = self.cleaned_data.get('liaison_name', '')
        # check for tag within parenthesis to ensure name was selected from the list 
        m = re.search(r'(\d+)', name)
        if name and not m:
            raise forms.ValidationError("You must select an entry from the list!") 
        return name

    def clean_affiliation(self):
        affiliation = self.cleaned_data.get('affiliation', '')
        # give error if field ends with "Liaison", application adds this label 
        m = re.search(r'[L|l]iaison$', affiliation)
        if affiliation and m:
            raise forms.ValidationError("Don't use 'Liaison' in field.  Application adds this.") 
        return affiliation

class ChairForm(forms.Form):
    chair_name = forms.CharField(max_length=100,label='Name',help_text="To see a list of people type the first name, or last name, or both.")

    # set css class=name-autocomplete for name field (to provide select list)
    def __init__(self, *args, **kwargs):
        super(ChairForm, self).__init__(*args, **kwargs)
        self.fields['chair_name'].widget.attrs['class'] = 'name-autocomplete'

    def clean_chair_name(self):
        name = self.cleaned_data.get('chair_name', '')
        # check for tag within parenthesis to ensure name was selected from the list 
        m = re.search(r'(\d+)', name)
        if name and not m:
            raise forms.ValidationError("You must select an entry from the list!") 
        return name
