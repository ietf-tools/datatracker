from django import forms
from django.forms.formsets import BaseFormSet

from ietf.doc.models import *
from ietf.name.models import IntendedStdLevelName
from ietf.group.models import Group

from sec.utils.ams_utils import get_base, get_revision
from sec.groups.forms import RoleForm, get_person

import datetime
import re
from os.path import splitext

# ---------------------------------------------
# Select Choices 
# ---------------------------------------------
WITHDRAW_CHOICES = (('ietf','Withdraw by IETF'),('author','Withdraw by Author'))

# ---------------------------------------------
# Custom Fields 
# ---------------------------------------------
class DocumentField(forms.FileField):
    '''A validating document upload field'''
    
    def __init__(self, unique=False, *args, **kwargs):
        self.extension = kwargs.pop('extension')
        self.filename = kwargs.pop('filename')
        self.rev = kwargs.pop('rev')
        super(DocumentField, self).__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        file = super(DocumentField, self).clean(data,initial)
        if file:
            # validate general file format
            m = re.search(r'.*-\d{2}\.(txt|pdf|ps|xml)', file.name)
            if not m:
                raise forms.ValidationError('File name must be in the form base-NN.[txt|pdf|ps|xml]')
                
            # ensure file extension is correct
            base,ext = os.path.splitext(file.name)
            if ext != self.extension:
                raise forms.ValidationError('Incorrect file extension: %s' % ext)

            # if this isn't a brand new submission we need to do some extra validations
            if self.filename:
                # validate filename
                if base[:-3] != self.filename:
                    raise forms.ValidationError, "Filename: %s doesn't match Draft filename." % base[:-3]
                # validate revision
                next_revision = str(int(self.rev)+1).zfill(2)
                if base[-2:] != next_revision:
                    raise forms.ValidationError, "Expected revision # %s" % (next_revision)
                
        return file

class GroupModelChoiceField(forms.ModelChoiceField):
    '''
    Custom ModelChoiceField sets queryset to include all active workgroups and the 
    individual submission group, none.  Displays group acronyms as choices.  Call it without the
    queryset argument, for example:
    
    group = GroupModelChoiceField(required=True)
    '''
    def __init__(self, *args, **kwargs):
        kwargs['queryset'] = Group.objects.filter(type__in=('wg','individ'),state__in=('bof','proposed','active')).order_by('acronym')
        super(GroupModelChoiceField, self).__init__(*args, **kwargs)
    
    def label_from_instance(self, obj):
        return obj.acronym

class AliasModelChoiceField(forms.ModelChoiceField):
    '''
    Custom ModelChoiceField, just uses Alias name in the select choices as opposed to the 
    more confusing alias -> doc format used by DocAlias.__unicode__
    '''    
    def label_from_instance(self, obj):
        return obj.name
        
# ---------------------------------------------
# Forms 
# ---------------------------------------------
class AddModelForm(forms.ModelForm):
    start_date = forms.DateField()
    group = GroupModelChoiceField(required=True,help_text='Use group "none" for Individual Submissions')
    
    class Meta:
        model = Document
        fields = ('title','group','stream','start_date','pages','abstract','internal_comments')
       
    # use this method to set attrs which keeps other meta info from model.  
    def __init__(self, *args, **kwargs):
        super(AddModelForm, self).__init__(*args, **kwargs)
        self.fields['title'].label='Document Name'
        self.fields['title'].widget=forms.Textarea()
        self.fields['start_date'].initial=datetime.date.today
        self.fields['pages'].label='Number of Pages'
        self.fields['internal_comments'].label='Comments'

class AuthorForm(forms.Form):
    '''
    The generic javascript for populating the email list based on the name selected expects to
    see an id_email field
    '''
    person = forms.CharField(max_length=50,widget=forms.TextInput(attrs={'class':'name-autocomplete'}),help_text="To see a list of people type the first name, or last name, or both.")
    email = forms.CharField(widget=forms.Select(),help_text="Select an email")
        
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

class EditModelForm(forms.ModelForm):
    #expiration_date = forms.DateField(required=False)
    state = forms.ModelChoiceField(queryset=State.objects.filter(type='draft'),empty_label=None)
    iesg_state = forms.ModelChoiceField(queryset=State.objects.filter(type='draft-iesg'),required=False)
    group = GroupModelChoiceField(required=True)
    review_by_rfc_editor = forms.BooleanField(required=False)
    shepherd = forms.CharField(max_length=100,widget=forms.TextInput(attrs={'class':'name-autocomplete'}),help_text="To see a list of people type the first name, or last name, or both.",required=False)
    
    class Meta:
        model = Document
        fields = ('title','group','ad','shepherd','notify','stream','review_by_rfc_editor','name','rev','pages','intended_std_level','abstract','internal_comments')
                 
    # use this method to set attrs which keeps other meta info from model.  
    def __init__(self, *args, **kwargs):
        super(EditModelForm, self).__init__(*args, **kwargs)
        self.fields['ad'].queryset = Person.objects.filter(role__name='ad')
        self.fields['title'].label='Document Name'
        self.fields['title'].widget=forms.Textarea()
        self.fields['rev'].widget.attrs['size'] = 2
        self.fields['abstract'].widget.attrs['cols'] = 72
        self.initial['state'] = self.instance.get_state()
        self.initial['iesg_state'] = self.instance.get_state('draft-iesg')
        if self.instance.shepherd:
            self.initial['shepherd'] = "%s - (%s)" % (self.instance.shepherd.name, self.instance.shepherd.id)
        
        # setup special fields
        if self.instance:
            # setup replaced
            self.fields['review_by_rfc_editor'].initial = bool(self.instance.tags.filter(slug='rfc-rev'))
            
    def save(self, force_insert=False, force_update=False, commit=True):
        m = super(EditModelForm, self).save(commit=False)
        state = self.cleaned_data['state']
        iesg_state = self.cleaned_data['iesg_state']
        
        if 'state' in self.changed_data:
            m.set_state(state)
        
        # note we're not sending notices here, is this desired
        if 'iesg_state' in self.changed_data:
            if iesg_state == None:
                m.unset_state('draft-iesg')
            else:
                m.set_state(iesg_state)
            
        if 'review_by_rfc_editor' in self.changed_data:
            if self.cleaned_data.get('review_by_rfc_editor',''):
                m.tags.add('rfc-rev')
            else:
                m.tags.remove('rfc-rev')
        
        m.time = datetime.datetime.now()
        # handle replaced by
        
        if commit:
            m.save()
        return m

    # field must contain filename of existing draft
    def clean_replaced_by(self):
        name = self.cleaned_data.get('replaced_by', '')
        if name and not InternetDraft.objects.filter(filename=name):
            raise forms.ValidationError("ERROR: Draft does not exist") 
        return name
        
    # check for id within parenthesis to ensure name was selected from the list 
    def clean_shepherd(self):
        person = self.cleaned_data.get('shepherd', '')
        m = re.search(r'(\d+)', person)
        if person and not m:
            raise forms.ValidationError("You must select an entry from the list!") 
        
        # return person object
        return get_person(person)
        
    def clean(self):
        super(EditModelForm, self).clean()
        cleaned_data = self.cleaned_data
        """
        expiration_date = cleaned_data.get('expiration_date','')
        status = cleaned_data.get('status','')
        replaced = cleaned_data.get('replaced',False)
        replaced_by = cleaned_data.get('replaced_by','')
        replaced_status_object = IDStatus.objects.get(status_id=5)
        expired_status_object = IDStatus.objects.get(status_id=2)
        # this condition seems to be valid
        #if expiration_date and status != expired_status_object:
        #    raise forms.ValidationError('Expiration Date set but status is %s' % (status))
        if status == expired_status_object and not expiration_date:
            raise forms.ValidationError('Status is Expired but Expirated Date is not set')
        if replaced and status != replaced_status_object:
            raise forms.ValidationError('You have checked Replaced but status is %s' % (status))
        if replaced and not replaced_by:
            raise forms.ValidationError('You have checked Replaced but Replaced By field is empty')
        """
        return cleaned_data

class EmailForm(forms.Form):
    # max_lengths come from db limits, cc is not limited
    to = forms.CharField(max_length=255)
    cc = forms.CharField(required=False)
    subject = forms.CharField(max_length=255)
    body = forms.CharField(widget=forms.Textarea())

class ExtendForm(forms.Form):
    expiration_date = forms.DateField()
    
class ReplaceForm(forms.Form):
    replaced = AliasModelChoiceField(DocAlias.objects.none(),empty_label=None,help_text='This document may have more than one alias.  Be sure to select the correct alias to replace.')
    replaced_by = forms.CharField(max_length=100,help_text='Enter the filename of the Draft which replaces this one.')

    def __init__(self, *args, **kwargs):
        self.draft = kwargs.pop('draft')
        super(ReplaceForm, self).__init__(*args, **kwargs)
        self.fields['replaced'].queryset = DocAlias.objects.filter(document=self.draft)
        
    # field must contain filename of existing draft
    def clean_replaced_by(self):
        name = self.cleaned_data.get('replaced_by', '')
        try:
            doc = Document.objects.get(name=name)
        except Document.DoesNotExist:
            raise forms.ValidationError("ERROR: Draft does not exist: %s" % name)
        if name == self.draft.name:
            raise forms.ValidationError("ERROR: A draft can't replace itself")
        return doc

class BaseRevisionModelForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ('title','pages','abstract')

class RevisionModelForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ('title','pages','abstract')
    
    # use this method to set attrs which keeps other meta info from model.  
    def __init__(self, *args, **kwargs):
        super(RevisionModelForm, self).__init__(*args, **kwargs)
        self.fields['title'].label='Document Name'
        self.fields['title'].widget=forms.Textarea()
        self.fields['pages'].label='Number of Pages'
        
class RfcModelForm(forms.ModelForm):
    rfc_number = forms.IntegerField()
    rfc_published_date = forms.DateField(initial=datetime.datetime.now)
    group = GroupModelChoiceField(required=True)
    
    class Meta:
        model = Document
        fields = ('title','group','pages','std_level','internal_comments')
    
    # use this method to set attrs which keeps other meta info from model.  
    def __init__(self, *args, **kwargs):
        super(RfcModelForm, self).__init__(*args, **kwargs)
        self.fields['title'].widget = forms.Textarea()
        self.fields['std_level'].required = True
    
    def save(self, force_insert=False, force_update=False, commit=True):
        obj = super(RfcModelForm, self).save(commit=False)
        
        # create DocAlias
        DocAlias.objects.create(document=self.instance,name="rfc%d" % self.cleaned_data['rfc_number'])
        
        if commit:
            obj.save()
        return obj
        
    def clean_rfc_number(self):
        rfc_number = self.cleaned_data['rfc_number']
        if DocAlias.objects.filter(name='rfc' + str(rfc_number)):
            raise forms.ValidationError("RFC %d already exists" % rfc_number)
        return rfc_number
        
class RfcObsoletesForm(forms.Form):
    relation = forms.ModelChoiceField(queryset=DocRelationshipName.objects.filter(slug__in=('updates','obs')),required=False)
    rfc = forms.IntegerField(required=False)
    
    # ensure that RFC exists
    def clean_rfc(self):
        rfc = self.cleaned_data.get('rfc','')
        if rfc:
            if not Document.objects.filter(docalias__name="rfc%s" % rfc):
                raise forms.ValidationError("RFC does not exist")
        return rfc
    
    def clean(self):
        super(RfcObsoletesForm, self).clean()
        cleaned_data = self.cleaned_data
        relation = cleaned_data.get('relation','')
        rfc = cleaned_data.get('rfc','')
        if (relation and not rfc) or (rfc and not relation):
            raise forms.ValidationError('You must select a relation and enter RFC #')
        return cleaned_data

class SearchForm(forms.Form):
    intended_std_level = forms.ModelChoiceField(queryset=IntendedStdLevelName.objects,label="Intended Status",required=False)
    document_title = forms.CharField(max_length=80,label='Document Title',required=False)
    group = forms.CharField(max_length=12,required=False)
    filename = forms.CharField(max_length=80,required=False)
    state = forms.ModelChoiceField(queryset=State.objects.filter(type='draft'),required=False)
    revision_date_start = forms.DateField(label='Revision Date (start)',required=False)
    revision_date_end = forms.DateField(label='Revision Date (end)',required=False)

class UploadForm(forms.Form):
    txt = DocumentField(label=u'.txt format', required=True,extension='.txt',filename=None,rev=None)
    xml = DocumentField(label=u'.xml format', required=False,extension='.xml',filename=None,rev=None)
    pdf = DocumentField(label=u'.pdf format', required=False,extension='.pdf',filename=None,rev=None)
    ps = DocumentField(label=u'.ps format', required=False,extension='.ps',filename=None,rev=None)

    def __init__(self, *args, **kwargs):
        if 'draft' in kwargs:
            self.draft = kwargs.pop('draft')
        else:
            self.draft = None
        super(UploadForm, self).__init__(*args, **kwargs)
        if self.draft:
            for field in self.fields.itervalues():
                field.filename = self.draft.name
                field.rev = self.draft.rev
                
        
    def clean(self):
        # Checks that all files have the same base
        if any(self.errors):
            # Don't bother validating unless each field is valid on its own
            return
        txt = self.cleaned_data['txt']
        xml = self.cleaned_data['xml']
        pdf = self.cleaned_data['pdf']
        ps = self.cleaned_data['ps']
        
        # we only need to do these validations for new drafts
        if not self.draft:
            names = []
            for file in (txt,xml,pdf,ps):
                if file:
                    base = splitext(file.name)[0]
                    if base not in names:
                        names.append(base)
                    
            if len(names) > 1:
                raise forms.ValidationError, "All files must have the same base name"
        
            # ensure that the basename is unique
            base = splitext(txt.name)[0]
            if Document.objects.filter(name=base[:-3]):
                raise forms.ValidationError, "This doucment filename already exists: %s" % base[:-3]
            
            # ensure that rev is 00
            if base[-2:] != '00':
                raise forms.ValidationError, "New Drafts must start with 00 revision number."
        
        return self.cleaned_data

class WithdrawForm(forms.Form):
    type = forms.CharField(widget=forms.Select(choices=WITHDRAW_CHOICES),help_text='Select which type of withdraw to perform')

