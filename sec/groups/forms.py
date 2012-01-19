from django import forms
from django.db.models import Q

from redesign.group.models import Group, GroupMilestone, Role
from redesign.name.models import GroupStateName, GroupTypeName, RoleName
from redesign.person.models import Person, Email

from sec.areas.forms import AWPForm

import re

# ---------------------------------------------
# Select Choices 
# ---------------------------------------------
# Get select options from db.  add blank options to assist search
# ie. so search will return groups of all types if that's what we want

AREA_CHOICES = list(Group.objects.filter(type='area',state='active').values_list('acronym','name'))
SEARCH_AREA_CHOICES = AREA_CHOICES[:]
SEARCH_AREA_CHOICES.insert(0,('',''))

TYPE_CHOICES = list(GroupTypeName.objects.filter(name__in=('WG','AG','Team')).values_list('slug', 'name')) 
SEARCH_TYPE_CHOICES = TYPE_CHOICES[:]
SEARCH_TYPE_CHOICES.insert(0,('',''))
STATE_CHOICES = list(GroupStateName.objects.values_list('slug', 'name'))
STATE_CHOICES.insert(0,('',''))

# only "Active" status is valid for new groups 
NEW_STATUS_CHOICES = (('1', 'Active'),) 
ROLE_CHOICES = (
    ('WGChair', 'Chair'),
    ('WGEditor', 'Document Editor'),
    ('WGTechAdvisor', 'Technical Advisor'),
    ('WGSecretary', 'Secretary'))

SEARCH_MEETING_CHOICES = (('',''),('NO','NO'),('YES','YES'))
MEETING_CHOICES = (('NO','NO'),('YES','YES'))

# ---------------------------------------------
# Functions
# ---------------------------------------------
"""
def get_person(name):
    '''This function takes a string which is in the name autocomplete format "name - email (tag)" and returns a person object'''
 
    match = re.search(r'\((\d+)\)', name)
    if not match:
        return None
    tag = match.group(1)
    try:
       person = PersonOrOrgInfo.objects.get(person_or_org_tag=tag)
    except (PersonOrOrgInfo.ObjectDoesNoExist, PersonOrOrgInfo.MultipleObjectsReturned):
        return None
    return person

"""
# ---------------------------------------------
# Forms
# ---------------------------------------------

class DescriptionForm (forms.Form):
    description = forms.CharField(widget=forms.Textarea(attrs={'rows':'20'}),required=True)

class GroupMilestoneForm(forms.ModelForm):
    class Meta:
        model = GroupMilestone
        exclude = ('done', 'last_modified_date')

    # use this method to set attrs which keeps other meta info from model.  
    def __init__(self, *args, **kwargs):
        super(GroupMilestoneForm, self).__init__(*args, **kwargs)
        self.fields['desc'].widget=forms.TextInput(attrs={'size':'60'})
        self.fields['expected_due_date'].widget.attrs['size'] = 10
        self.fields['done_date'].widget.attrs['size'] = 10

    # override save.  set done=Done if done_date set and not equal to "0000-00-00"
    def save(self, force_insert=False, force_update=False, commit=True):
        m = super(GroupMilestoneForm, self).save(commit=False)
        if 'done_date' in self.changed_data:
            if self.cleaned_data.get('done_date',''):
                m.done = 'Done'
            else:
                m.done = ''
        if commit:
            m.save()
        return m

class GroupRoleForm(forms.Form):
    role_type = forms.CharField(max_length=25,widget=forms.Select(choices=ROLE_CHOICES),required=False)
    role_name = forms.CharField(max_length=100,label='Name',help_text="To see a list of people type the first name, or last name, or both.")
    group = forms.CharField(widget=forms.HiddenInput())

    # set css class=name-autocomplete for name field (to provide select list)
    def __init__(self, *args, **kwargs):
        super(GroupRoleForm, self).__init__(*args, **kwargs)
        self.fields['role_name'].widget.attrs['class'] = 'name-autocomplete'

    # check for tag within parenthesis to ensure name was selected from the list 
    def clean_role_name(self):
        name = self.cleaned_data.get('role_name', '')
        m = re.search(r'(\d+)', name)
        if name and not m:
            raise forms.ValidationError("You must select an entry from the list!") 
        return name

    def clean(self):
        # here we abort if there are any errors with individual fields
        # One predictable problem is that the user types a name rather then
        # selecting one from the list, as instructed to do.  We need to abort
        # so the error is displayed before trying to call get_person()
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return

        cleaned_data = self.cleaned_data
        name = cleaned_data.get('role_name')
        type = cleaned_data.get('role_type')
        group = cleaned_data.get('group')
        person = get_person(name)

        if type == 'Chair':
            if WGChair.objects.filter(person=person,group_acronym=group):
                raise forms.ValidationError('ERROR: This is a duplicate entry')

        if type == 'Document Editor':
            if WGEditor.objects.filter(person=person,group_acronym=group):
                raise forms.ValidationError('ERROR: This is a duplicate entry')

        if type == 'Technical Advisor':
            if WGTechAdvisor.objects.filter(person=person,group_acronym=group):
                raise forms.ValidationError('ERROR: This is a duplicate entry')

        if type == 'Secretary':
            if WGSecretary.objects.filter(person=person,group_acronym=group):
                raise forms.ValidationError('ERROR: This is a duplicate entry')

        # Always return the full collection of cleaned data.
        return cleaned_data

class GroupModelForm(forms.ModelForm):
    type = forms.ModelChoiceField(queryset=GroupTypeName.objects.filter(slug__in=('rg','wg')),empty_label=None)
    parent = forms.ModelChoiceField(queryset=Group.objects.filter(Q(type='area',state='active')|Q(acronym='irtf')))
    ad = forms.ModelChoiceField(queryset=Person.objects.filter(role__name='ad'))
    state = forms.ModelChoiceField(queryset=GroupStateName.objects.filter(name__in=('bof','proposed','active')))
    
    class Meta:
        model = Group
        fields = ('acronym','name','type','state','parent','ad','list_email','list_subscribe','list_archive','comments')
    
    def __init__(self, *args, **kwargs):
        super(GroupModelForm, self).__init__(*args, **kwargs)
        self.fields['list_email'].label = 'List Email'
        self.fields['list_subscribe'].label = 'List Subscribe'
        self.fields['list_archive'].label = 'List Archive'
        self.fields['ad'].label = 'Area Director'
        self.fields['comments'].widget.attrs['rows'] = 3
        self.fields['parent'].label = 'Area'
        
        # make adjustments for edit
        if self.instance:
            self.fields['state'].queryset = GroupStateName.objects.exclude(name__in=('dormant','unknown'))
            
    def clean(self):
        if any(self.errors):
            return self.cleaned_data
        super(GroupModelForm, self).clean()
            
        type = self.cleaned_data['type']
        parent = self.cleaned_data['parent']
        state = self.cleaned_data['state']
        irtf_area = Group.objects.get(acronym='irtf')
        
        # ensure proper parent for group type
        if type.slug == 'rg' and parent != irtf_area:
            raise forms.ValidationError('The Area for a research group must be %s' % irtf_area)
            
        if type.slug == 'rg' and state.name != 'active':
            raise forms.ValidationError('You must choose "active" for research group state')
            
        return self.cleaned_data

class RoleForm(forms.ModelForm):
    person = forms.CharField(max_length=50,widget=forms.TextInput(attrs={'class':'name-autocomplete'}))
        
    class Meta:
        model = Role
        
    def __init__(self, *args, **kwargs):
        super(RoleForm, self).__init__(*args,**kwargs)
        self.fields['name'].label = 'Role Name'
        self.fields['name'].queryset = RoleName.objects.filter(slug__in=('chair','editor','secr','techadv'))
        self.fields['email'].queryset = Email.objects.none()
        
        if self.initial:
            self.fields['email'].queryset = Email.objects.filter(person=self.instance.person)
            self.initial['person'] = self.instance.person.name
                
class SearchForm(forms.Form):
    group_acronym = forms.CharField(max_length=12,required=False)
    group_name = forms.CharField(max_length=80,required=False)
    primary_area = forms.CharField(max_length=80,widget=forms.Select(choices=SEARCH_AREA_CHOICES),required=False) 
    type = forms.CharField(max_length=25,widget=forms.Select(choices=SEARCH_TYPE_CHOICES),required=False)
    #meeting_scheduled = forms.BooleanField(required=False)
    meeting_scheduled = forms.CharField(widget=forms.Select(choices=SEARCH_MEETING_CHOICES),required=False)
    state = forms.CharField(max_length=25,widget=forms.Select(choices=STATE_CHOICES),required=False)

