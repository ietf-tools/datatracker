from django import forms

from ietf.person.models import Person, Email
from ietf.group.models import Group, GroupURL
from ietf.name.models import GroupTypeName, GroupStateName

import datetime
import re

STATE_CHOICES = (
    (1, 'Active'),
    (2, 'Concluded')
)


class AWPForm(forms.ModelForm):
    class Meta:
        model = GroupURL

    def __init__(self, *args, **kwargs):
        super(AWPForm, self).__init__(*args,**kwargs)
        self.fields['url'].widget.attrs['width'] = 40
        self.fields['name'].widget.attrs['width'] = 40
        self.fields['url'].required = False
        self.fields['name'].required = False
        
    # Validation: url without description and vice-versa 
    def clean(self):
        super(AWPForm, self).clean()
        cleaned_data = self.cleaned_data
        url = cleaned_data.get('url')
        name = cleaned_data.get('name')

        if (url and not name) or (name and not url):
            raise forms.ValidationError('You must fill out URL and Name')

        # Always return the full collection of cleaned data.
        return cleaned_data


class AreaForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ('acronym','name','state','comments')

    # use this method to set attrs which keeps other meta info from model.  
    def __init__(self, *args, **kwargs):
        super(AreaForm, self).__init__(*args, **kwargs)
        self.fields['state'].queryset = GroupStateName.objects.filter(slug__in=('active','conclude'))
        self.fields['state'].empty_label = None
        self.fields['comments'].widget.attrs['rows'] = 2

"""
    # Validation: status and conclude_date must agree
    def clean(self):
        super(AreaForm, self).clean()
        cleaned_data = self.cleaned_data
        concluded_date = cleaned_data.get('concluded_date')
        state = cleaned_data.get('state')
        concluded_status_object = AreaStatus.objects.get(status_id=2)

        if concluded_date and status != concluded_status_object:
            raise forms.ValidationError('Concluded Date set but status is %s' % (status.status_value))

        if status == concluded_status_object and not concluded_date:
            raise forms.ValidationError('Status is Concluded but Concluded Date not set.')

        # Always return the full collection of cleaned data.
        return cleaned_data

"""
class AWPAddModelForm(forms.ModelForm):
    class Meta:
        model = GroupURL
        fields = ('url', 'name')
        
# for use with Add view, ModelForm doesn't work because the parent type hasn't been created yet
# when initial screen is displayed
class AWPAddForm(forms.Form):
    url = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'size':'40'}))
    description = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'size':'40'}))
 
    # Validation: url without description and vice-versa 
    def clean(self):
        super(AWPAddForm, self).clean()
        cleaned_data = self.cleaned_data
        url = cleaned_data.get('url')
        description = cleaned_data.get('description')

        if (url and not description) or (description and not url):
            raise forms.ValidationError('You must fill out URL and Description')

        # Always return the full collection of cleaned data.
        return cleaned_data

class AddAreaModelForm(forms.ModelForm):
    start_date = forms.DateField()
    
    class Meta:
        model = Group
        fields = ('acronym','name','state','start_date','comments')
        
    def __init__(self, *args, **kwargs):
        super(AddAreaModelForm, self).__init__(*args, **kwargs)
        self.fields['acronym'].required = True
        self.fields['name'].required = True
        self.fields['start_date'].required = True
        self.fields['start_date'].initial = datetime.date.today
        
    def clean_acronym(self):
        acronym = self.cleaned_data['acronym']
        if Group.objects.filter(acronym=acronym):
            raise forms.ValidationError("This acronym already exists.  Enter a unique one.")
        r1 = re.compile(r'[a-zA-Z\-\. ]+$')
        if not r1.match(acronym):
            raise forms.ValidationError("Enter a valid acronym (only letters,period,hyphen allowed)")
        return acronym
        
    def clean_name(self):
        name = self.cleaned_data['name']
        if Group.objects.filter(name=name):
            raise forms.ValidationError("This name already exists.  Enter a unique one.")
        r1 = re.compile(r'[a-zA-Z\-\. ]+$')
        if name and not r1.match(name):
            raise forms.ValidationError("Enter a valid name (only letters,period,hyphen allowed)")
        return name
        
    def save(self, force_insert=False, force_update=False, commit=True):
        area = super(AddAreaModelForm, self).save(commit=False)
        area_type = GroupTypeName.objects.get(name='area')
        area.type = area_type
        if commit:
            area.save()
        return area
        
class AddAreaForm(forms.Form):
    acronym = forms.CharField(max_length=16,required=True)
    name = forms.CharField(max_length=80,required=True)
    status = forms.IntegerField(widget=forms.Select(choices=STATE_CHOICES),required=True)
    start_date = forms.DateField()
    comments = forms.CharField(widget=forms.Textarea(attrs={'rows':'1'}),required=False)

    def clean_acronym(self):
        # get name, strip leading and trailing spaces
        name = self.cleaned_data.get('acronym', '').strip()
        # check for invalid characters
        r1 = re.compile(r'[a-zA-Z\-\. ]+$')
        if name and not r1.match(name):
            raise forms.ValidationError("Enter a valid acronym (only letters,period,hyphen allowed)") 
        # ensure doesn't already exist
        if Acronym.objects.filter(acronym=name):
            raise forms.ValidationError("This acronym already exists.  Enter a unique one.") 
        return name
        
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
