import re

from django import forms
from django.db.models import Count

from ietf.group.models import Group, Role
from ietf.name.models import GroupStateName, GroupTypeName, RoleName
from ietf.person.models import Person, Email
from ietf.liaisons.models import LiaisonStatementGroupContacts


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


class GroupModelForm(forms.ModelForm):
    type = forms.ModelChoiceField(queryset=GroupTypeName.objects.all(),empty_label=None)
    parent = forms.ModelChoiceField(queryset=Group.objects.all(),required=False)
    ad = forms.ModelChoiceField(queryset=Person.objects.filter(role__name='ad',role__group__state='active',role__group__type='area'),required=False)
    state = forms.ModelChoiceField(queryset=GroupStateName.objects.exclude(slug__in=('dormant','unknown')),empty_label=None)
    liaison_contacts = forms.CharField(max_length=255,required=False,label='Default Liaison Contacts')
    
    class Meta:
        model = Group
        fields = ('acronym','name','type','state','parent','ad','list_email','list_subscribe','list_archive','description','comments')
    
    def __init__(self, *args, **kwargs):
        super(GroupModelForm, self).__init__(*args, **kwargs)
        self.fields['list_email'].label = 'List Email'
        self.fields['list_subscribe'].label = 'List Subscribe'
        self.fields['list_archive'].label = 'List Archive'
        self.fields['ad'].label = 'Area Director'
        self.fields['comments'].widget.attrs['rows'] = 3
        self.fields['parent'].label = 'Area / Parent'
        self.fields['parent'].choices = get_parent_group_choices()

        if self.instance.pk:
            lsgc = self.instance.liaisonstatementgroupcontacts_set.first() # there can only be one
            if lsgc:
                self.fields['liaison_contacts'].initial = lsgc.contacts
        
    def clean_acronym(self):
        acronym = self.cleaned_data['acronym']
        if any(x.isupper() for x in acronym):
            raise forms.ValidationError('Capital letters not allowed in group acronym')
        return acronym

    def clean_parent(self):
        parent = self.cleaned_data['parent']
        type = self.cleaned_data['type']
        
        if type.features.acts_like_wg and not parent:
            raise forms.ValidationError("This field is required.")
        
        return parent
        
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
            
        # an RG can't be proposed
        if type.slug == 'rg' and state.slug not in ('active','conclude'):
            raise forms.ValidationError('You must choose "active" or "concluded" for research group state')
            
        return self.cleaned_data
    
    def save(self, force_insert=False, force_update=False, commit=True):
        obj = super(GroupModelForm, self).save(commit=False)
        if commit:
            obj.save()
        contacts = self.cleaned_data.get('liaison_contacts')
        if contacts:
            try:
                lsgc = LiaisonStatementGroupContacts.objects.get(group=self.instance)
                lsgc.contacts = contacts
                lsgc.save()
            except LiaisonStatementGroupContacts.DoesNotExist:
                LiaisonStatementGroupContacts.objects.create(group=self.instance,contacts=contacts)
        elif LiaisonStatementGroupContacts.objects.filter(group=self.instance):
            LiaisonStatementGroupContacts.objects.filter(group=self.instance).delete()
        
        return obj

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
