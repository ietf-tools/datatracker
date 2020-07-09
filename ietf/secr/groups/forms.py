import re

from django import forms
from django.db.models import Count

from ietf.group.models import Group, Role
from ietf.name.models import GroupStateName, GroupTypeName, RoleName
from ietf.person.models import Person, Email


# ---------------------------------------------
# Select Choices 
# ---------------------------------------------
SEARCH_MEETING_CHOICES = (('',''),('NO','NO'),('YES','YES'))

# ---------------------------------------------
# Functions
# ---------------------------------------------
def get_person(name):
    '''
    This function takes a string which is in the name autocomplete format "name - (id)"
    and returns a person object
    '''
 
    match = re.search(r'\((\d+)\)', name)
    if not match:
        return None
    id = match.group(1)
    try:
       person = Person.objects.get(id=id)
    except (Person.ObjectDoesNoExist, Person.MultipleObjectsReturned):
        return None
    return person

def get_parent_group_choices():
    area_choices = [(g.id, g.name) for g in Group.objects.filter(type='area',state='active')]
    other_parents = Group.objects.annotate(children=Count('group')).filter(children__gt=0).order_by('name').exclude(type='area')
    other_choices = [(g.id, g.name) for g in other_parents]
    choices = (('Working Group Areas',area_choices),('Other',other_choices))
    return choices

# ---------------------------------------------
# Forms
# ---------------------------------------------

class DescriptionForm (forms.Form):
    description = forms.CharField(widget=forms.Textarea(attrs={'rows':'20'}),required=True, strip=False)



class RoleForm(forms.Form):
    name = forms.ModelChoiceField(RoleName.objects.filter(slug__in=('chair','editor','secr','techadv')),empty_label=None)
    person = forms.CharField(max_length=50,widget=forms.TextInput(attrs={'class':'name-autocomplete'}),help_text="To see a list of people type the first name, or last name, or both.")
    email = forms.CharField(widget=forms.Select(),help_text="Select an email")
    group_acronym = forms.CharField(widget=forms.HiddenInput(),required=False)
    
    def __init__(self, *args, **kwargs):
        self.group = kwargs.pop('group')
        super(RoleForm, self).__init__(*args,**kwargs)
        # this form is re-used in roles app, use different roles in select
        if self.group.features.custom_group_roles:
            self.fields['name'].queryset = RoleName.objects.all()
        
    # check for id within parenthesis to ensure name was selected from the list 
    def clean_person(self):
        person = self.cleaned_data.get('person', '')
        m = re.search(r'(\d+)', person)
        if person and not m:
            raise forms.ValidationError("You must select an entry from the list!") 
        
        # return person object
        return get_person(person)
    
    # check that email exists and return the Email object
    def clean_email(self):
        email = self.cleaned_data['email']
        try:
            obj = Email.objects.get(address=email)
        except Email.ObjectDoesNoExist:
            raise forms.ValidationError("Email address not found!")
        
        # return email object
        return obj
    
    def clean(self):
        # here we abort if there are any errors with individual fields
        # One predictable problem is that the user types a name rather then
        # selecting one from the list, as instructed to do.  We need to abort
        # so the error is displayed before trying to call get_person()
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return
        super(RoleForm, self).clean()
        cleaned_data = self.cleaned_data
        person = cleaned_data['person']
        email = cleaned_data['email']
        name = cleaned_data['name']
        group_acronym = cleaned_data['group_acronym']
        
        if email.person != person:
            raise forms.ValidationError('ERROR: The person associated with the chosen email address is different from the chosen person')

        if Role.objects.filter(name=name,group=self.group,person=person,email=email):
            raise forms.ValidationError('ERROR: This is a duplicate entry')
        
        if not group_acronym:
            raise forms.ValidationError('You must select a group.')

        return cleaned_data
        
class SearchForm(forms.Form):
    group_acronym = forms.CharField(max_length=12,required=False)
    group_name = forms.CharField(max_length=80,required=False)
    primary_area = forms.ModelChoiceField(queryset=Group.objects.filter(type='area',state='active'),required=False)
    type = forms.ModelChoiceField(queryset=GroupTypeName.objects.all(),required=False)
    meeting_scheduled = forms.CharField(widget=forms.Select(choices=SEARCH_MEETING_CHOICES),required=False)
    state = forms.ModelChoiceField(queryset=GroupStateName.objects.exclude(slug__in=('dormant','unknown')),required=False)
