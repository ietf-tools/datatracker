from django import forms

from redesign.group.models import Group
from redesign.name.models import GroupStateName, GroupTypeName

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

class GroupModelForm (forms.ModelForm):
    # need to add this custom field
    # primary_area = forms.CharField(max_length=80,widget=forms.Select(choices=AREA_CHOICES),required=True) 
    # need to explicitly define status field so we can remove empty_label
    proposed_date = forms.DateField()
    started_date = forms.DateField()
    concluded_date = forms.DateField()
    # state = forms.ModelChoiceField(queryset=GroupStateName.objects,empty_label=None)
    # area_director = forms.CharField()
    
    class Meta:
        model = Group
        #exclude = ('charter')
        fields = ('acronym', 'name', 'type', 'proposed_date', 'started_date', 'concluded_date', 'state', 'iesg_state', 'parent', 'ad', 'list_email', 'list_subscribe', 'list_archive', 'comments')
    # use this method to set attrs which keeps other meta info from model.  
    def __init__(self, *args, **kwargs):
        super(GroupModelForm, self).__init__(*args, **kwargs)
        # take custom field, primary_area, from end of field list and
        # put in correct position
        # self.fields['area_director'].widget = forms.Select()
        # self.fields.keyOrder.insert(6, self.fields.keyOrder.pop())
            
    # Validation: status and dates must agree
    def clean(self):
        super(GroupModelForm, self).clean()
        cleaned_data = self.cleaned_data
        concluded_date = cleaned_data.get('concluded_date')
        dormant_date= cleaned_data.get('dormant_date')
        state = cleaned_data.get('state')
        concluded_status_object = WGStatus.objects.get(status_id=3)
        dormant_status_object = WGStatus.objects.get(status_id=2)

        if concluded_date and status != concluded_status_object:
            raise forms.ValidationError('Concluded Date set but status is %s' % (status))

        if status == concluded_status_object and not concluded_date:
            raise forms.ValidationError('Status is Concluded but Concluded Date not set.')

        if dormant_date and status != dormant_status_object:
            raise forms.ValidationError('Dormant Date set but status is %s' % (status))

        if status == dormant_status_object and not dormant_date:
            raise forms.ValidationError('Status is Dormant but Dormant Date not set.')

        # Always return the full collection of cleaned data.
        return cleaned_data
'''
class GoalMilestoneForm(forms.ModelForm):
    class Meta:
        model = GoalMilestone
        exclude = ('done', 'last_modified_date')

    # use this method to set attrs which keeps other meta info from model.  
    def __init__(self, *args, **kwargs):
        super(GoalMilestoneForm, self).__init__(*args, **kwargs)
        #self.fields['description'].widget.attrs['rows'] = 1
        self.fields['description'].widget=forms.TextInput(attrs={'size':'40'})
        self.fields['expected_due_date'].widget.attrs['size'] = 10
        self.fields['done_date'].widget.attrs['size'] = 10

    # override save.  set done=Done if done_date set and not equal to "0000-00-00"
    def save(self, force_insert=False, force_update=False, commit=True):
        m = super(GoalMilestoneForm, self).save(commit=False)
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

class NewGroupForm (forms.Form):
    group_acronym = forms.CharField(max_length=12,required=True)
    group_name = forms.CharField(max_length=80,widget=forms.TextInput(attrs={'size':'40'}),required=True)
    group_type = forms.CharField(max_length=25,widget=forms.Select(choices=TYPE_CHOICES),required=True)
    status = forms.CharField(max_length=25,widget=forms.Select(choices=NEW_STATUS_CHOICES),required=True)
    proposed_date = forms.DateField(required=False)
    primary_area = forms.CharField(max_length=80,widget=forms.Select(choices=SEARCH_AREA_CHOICES),required=True) 
    # area director options start out empty
    primary_area_director = forms.CharField(max_length=80,widget=forms.Select(),required=True) 
    #meeting_scheduled = forms.BooleanField(required=False)
    meeting_scheduled = forms.CharField(widget=forms.Select(choices=MEETING_CHOICES))
    # secondary area
    email_address = forms.EmailField(max_length=200,widget=forms.TextInput(attrs={'size':'40'}),required=False)
    email_subscribe = forms.CharField(max_length=120,widget=forms.TextInput(attrs={'size':'40'}),required=False)
    email_keyword = forms.CharField(max_length=50,widget=forms.TextInput(attrs={'size':'40'}),required=False)
    email_archive = forms.CharField(max_length=200,widget=forms.TextInput(attrs={'size':'40'}),required=False)
    comments = forms.CharField(widget=forms.Textarea(attrs={'rows':'2'}),required=False)

    def clean_group_acronym(self):
        # get name, strip leading and trailing spaces
        acronym = self.cleaned_data.get('group_acronym', '').strip()
        # check for invalid characters
        r1 = re.compile(r'[a-zA-Z0-9\-\.]+$')
        if acronym and not r1.match(acronym):
            raise forms.ValidationError("Enter a valid acronym (only letters,digits,period,hyphen allowed)") 
        # ensure doesn't already exist
        if Acronym.objects.filter(acronym=acronym):
            raise forms.ValidationError("This acronym already exists.  Enter a unique one.") 
        return acronym

    def clean(self):
        cleaned_data = self.cleaned_data
        proposed_date = cleaned_data['proposed_date']
        group_type = cleaned_data['group_type']
       
        if group_type == '1' and not proposed_date:
            raise forms.ValidationError("Proposed Date is required.") 
            
        # Always return the full collection of cleaned data.
        return cleaned_data
'''

class SearchForm (forms.Form):
    group_acronym = forms.CharField(max_length=12,required=False)
    group_name = forms.CharField(max_length=80,required=False)
    primary_area = forms.CharField(max_length=80,widget=forms.Select(choices=SEARCH_AREA_CHOICES),required=False) 
    type = forms.CharField(max_length=25,widget=forms.Select(choices=SEARCH_TYPE_CHOICES),required=False)
    #meeting_scheduled = forms.BooleanField(required=False)
    meeting_scheduled = forms.CharField(widget=forms.Select(choices=SEARCH_MEETING_CHOICES),required=False)
    state = forms.CharField(max_length=25,widget=forms.Select(choices=STATE_CHOICES),required=False)

