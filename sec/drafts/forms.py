import datetime
import re
from os.path import splitext

from django import forms
from django.forms.formsets import BaseFormSet

from redesign.doc.models import *
from redesign.name.models import IntendedStdLevelName

#from sec.utils.ams_utils import get_base, get_revision

# ---------------------------------------------
# Select Choices 
# ---------------------------------------------

IS_CHOICES = list(IntendedStdLevelName.objects.values_list('slug','name'))
SEARCH_IS_CHOICES = IS_CHOICES[:]
SEARCH_IS_CHOICES.insert(0,('',''))
STATUS_CHOICES = list(State.objects.filter(type='draft').values_list('slug', 'name')) 
SEARCH_STATUS_CHOICES = STATUS_CHOICES[:]
SEARCH_STATUS_CHOICES.insert(0,('',''))
"""
FILE_TYPE_CHOICES = (('.txt','.txt'),('.ps','.ps'),('.pdf','.pdf'))
WITHDRAW_CHOICES = (('ietf','Withdraw by IETF'),('author','Withdraw by Author'))
RFC_OBS_CHOICES = (('',''),('Obsoletes','Obsoletes'),('Updates','Updates'))

# build active group and area choices
groups = IETFWG.objects.filter(status=1).order_by('group_acronym')
all_groups = IETFWG.objects.all().order_by('group_acronym')
group_tuples = [(str(g.group_acronym.acronym_id),g.group_acronym.acronym) for g in groups]
GROUP_CHOICES = sorted(group_tuples, key=lambda group_tuples: group_tuples[1])
GROUP_CHOICES.insert(0,('',''))
areas = Area.objects.filter(status=1).order_by('area_acronym')
area_tuples = [(str(a.area_acronym.acronym_id),a.area_acronym.acronym) for a in areas]
AREA_CHOICES = sorted(area_tuples, key=lambda area_tuples: area_tuples[1])
AREA_CHOICES.insert(0,('',''))
# RFC group and area choices are different because the field is not a typical foreign key
rfc_group_tuples = [(g.group_acronym.acronym,g.group_acronym.acronym) for g in all_groups]
RFC_GROUP_CHOICES = sorted(rfc_group_tuples, key=lambda rfc_group_tuples: rfc_group_tuples[1])
RFC_GROUP_CHOICES.insert(0,('',''))
rfc_area_tuples = [(a.area_acronym.acronym,a.area_acronym.acronym) for a in areas]
RFC_AREA_CHOICES = sorted(rfc_area_tuples, key=lambda rfc_area_tuples: rfc_area_tuples[1])
RFC_AREA_CHOICES.insert(0,('',''))

ADD_GROUP_CHOICES = GROUP_CHOICES[:]
ADD_GROUP_CHOICES.insert(0,('',''))

# ---------------------------------------------
# Custom Fields 
# ---------------------------------------------
class DocumentField(forms.FileField):
    '''A validating document upload field'''
    valid_file_extensions = ('txt','pdf','ps','xml')
    unique = False
    
    def __init__(self, valid_file_extensions=None, unique=False, *args, **kwargs):
        super(DocumentField, self).__init__(*args, **kwargs)
        if unique:
            self.unique = unique
        if valid_file_extensions:
            self.valid_file_extensions = valid_file_extensions

    def clean(self, data, initial=None):
        file = super(DocumentField, self).clean(data,initial)
        # this is redundant to regex below
        #ext = splitext(file.name)[1][1:].lower()
        #if ext not in self.valid_file_extensions:
        #    raise forms.ValidationError('Document types accepted: ' + ', '.join(self.valid_file_extensions))
        if file:
            # ensure file name complies with standard format
            m = re.search(r'.*-\d{2}\.(txt|pdf|ps|xml)', file.name)
            if file and not m:
                raise forms.ValidationError('File name must be in the form base-NN.[txt|pdf|ps|xml]')
            # ensure that base name is not already used
            if self.unique:
                if InternetDraft.objects.filter(filename=get_base(file.name)).count() > 0:
                    raise forms.ValidationError('This document already exists! (%s)' % get_base(file.name)) 

        return file
# ---------------------------------------------
# Utility Functions 
# ---------------------------------------------


# ---------------------------------------------
# Forms 
# ---------------------------------------------

class AddForm(forms.Form):
    document_name = forms.CharField(max_length=80)
    group = forms.CharField(max_length=12)
    document_status = forms.CharField(widget=forms.Select(choices=(('1','Active'),)))
    review = forms.BooleanField(label='Under review by RFC Editor',required=False) 
    #file_name = forms.CharField(max_length=100)
    #revision = forms.CharField(max_length=2)
    #file_type = forms.CharField(max_length=4,widget=forms.Select(choices=FILE_TYPE_CHOICES))
    file = forms.FileField()
    start_date = forms.DateField()
    number_of_pages = forms.IntegerField()
    local_path = forms.CharField(max_length=40)
    abstract = forms.CharField()
    comments = forms.CharField()
    replaced_by = forms.CharField()

    def save():
        pass
        
class AddFileForm(forms.Form):
    # it appears the file input widget is not stylable via css
    file = DocumentField(unique=True)
    
class AddModelForm(forms.ModelForm):
    #file = DocumentField(unique=True)
    #file2 = DocumentField(required=False)

    class Meta:
        model = InternetDraft
        # remove replaced_by,review_by_rfc_editor fields from list per secretariat staff 09-27-10
        # remove local_path per Glen, staff 12-02-10
        fields = ('title','group','start_date','txt_page_count','abstract','comments')
       
    # use this method to set attrs which keeps other meta info from model.  
    def __init__(self, *args, **kwargs):
        super(AddModelForm, self).__init__(*args, **kwargs)
        self.fields['title'].label='Document Name'
        self.fields['title'].widget=forms.Textarea()
        self.fields['group'].widget=forms.Select(choices=ADD_GROUP_CHOICES)
        #self.fields['status'].label='Document Status'
        #self.fields['status'].widget=forms.Select(choices=(('1','Active'),))
        self.fields['start_date'].initial=datetime.date.today
        self.fields['txt_page_count'].label='Number of Pages'
        #self.fields['local_path'].help_text='/a/www/ietf-ftp/internet-drafts/...'
        #self.fields['file'].widget.attrs['size'] = 40
        #self.fields['file2'].widget.attrs['size'] = 40
        #self.fields['file2'].label='File (optional)'

    # Validation: all upload files must have the same base name
    '''
    def clean(self):
        super(AddModelForm, self).clean()
        cleaned_data = self.cleaned_data
        file = cleaned_data.get('file')
        file2 = cleaned_data.get('file2')
        if file and file2:
            if get_base(file.name) != get_base(file2.name):
                raise forms.ValidationError('Uploaded files must have the same base name.')

        # Always return the full collection of cleaned data.
        return cleaned_data

    
    def save(self, force_insert=False, force_update=False, commit=True):
        self.intended_status = IDIntendedStatus.objects.get(intended_status_id=8)
        assert False, self
        m = super(AddModelForm, self).save(commit=False)
        # do custom stuff
        if commit:
            m.save()
        return m
    '''

class AuthorForm(forms.Form):
    #author_name = forms.CharField(max_length=100,label='Name',help_text="To see a list of people type the first name, or last name, or both.")
    author_name = forms.CharField(max_length=100,label='Name')

    # set css class=name-autocomplete for name field (to provide select list)
    def __init__(self, *args, **kwargs):
        super(AuthorForm, self).__init__(*args, **kwargs)
        self.fields['author_name'].widget.attrs['class'] = 'name-autocomplete'

    # check for tag within parenthesis to ensure name was selected from the list 
    def clean_author_name(self):
        name = self.cleaned_data.get('author_name', '')
        m = re.search(r'(\d+)', name)
        if name and not m:
            raise forms.ValidationError("You must select an entry from the list!") 
        return name

class AuthorModelForm(forms.ModelForm):
    person = forms.CharField(max_length=100,label='Name')
    
    class Meta:
        model = IDAuthor
        exclude = ('author_order')
        
class BaseFileFormSet(BaseFormSet):
    '''
    This class is used when creating the formset factory for file upload,
    so we can call perform vailations across multiple file upload forms
    '''
    def __init__(self, request, *args, **kwargs):
        self.request = request
        super(BaseFileFormSet, self).__init__(*args, **kwargs)
        
    def clean(self):
        # Checks that all files have the same base
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return
        #assert False, self.total_form_count()
        names = []
        for i in range(0, self.total_form_count()):
            form = self.forms[i]
            if form.has_changed():
                file = form.cleaned_data['file']
                base = splitext(file.name)[0]
                if base not in names:
                    names.append(base)
        if len(names) > 1:
            raise forms.ValidationError, "All files must have the same base name"
        
        # if 'draft' exists in the session dictionary we are uploading files to an existing
        # draft (as opposed to adding a new draft) so do extra validations
        if 'draft' in self.request.session:
            draft = self.request.session['draft']
            # Check that the upload base filename is the same as the draft base filename
            upload_base = get_base(names[0])
            draft_base = draft.filename
            if upload_base != draft_base:
                raise forms.ValidationError, "The upload filename (%s) is different than the draft filename (%s)" % (upload_base, draft_base)
                
            # Check that the revision number of the upload file is current revision + 1
            next_revision = str(int(draft.revision)+1).zfill(2)
            if names[0][-2:] != next_revision:
                raise forms.ValidationError, "Expected revision # %s" % (next_revision)
            
class EditModelForm(forms.ModelForm):
    ''' NOTE: the replaced_by field is a foreign key to another InternetDraft object but
    we don't want to see a select widget with all drafts listed in the form.  Also it is 
    a BrokenForeignKey meaning many records in the db have "0" in this field which cuases
    problems for Django.  To handle this we exclude the model field replaced_by and 
    redefine as a CharField.  We also customize __init__, save, and clean_replaced_by
    functions to handle initialization and saving as a FK.
    '''
    # need to define expiration_date to set required=False
    expiration_date = forms.DateField(required=False)
    file = DocumentField(required=False)
    file2 = DocumentField(required=False)
    # need to explicitly define status field so we can remove empty_label
    status = forms.ModelChoiceField(queryset=IDStatus.objects,empty_label=None)
    file_type_txt = forms.BooleanField(required=False)
    file_type_pdf = forms.BooleanField(required=False)
    file_type_ps = forms.BooleanField(required=False)
    file_type_xml = forms.BooleanField(required=False)
    replaced_by = forms.CharField(required=False)
    lc_changes = forms.BooleanField(required=False)
    
    class Meta:
        model = InternetDraft
        # this list must include all fields that will not be presented on the edit
        # form, otherwise the values will be lost
        exclude = ('file_type','lc_sent_date','lc_changes','lc_expiration_date','b_sent_date',
                 'b_discussion_date','b_approve_date','replaced_by','wgreturn_date',
                 'dunn_sent_date','rfc_number','intended_status','expired_tombstone',
                 'local_path')
                 
    # use this method to set attrs which keeps other meta info from model.  
    def __init__(self, *args, **kwargs):
        super(EditModelForm, self).__init__(*args, **kwargs)
        self.fields['title'].label='Document Name'
        self.fields['title'].widget=forms.Textarea()
        self.fields['group'].widget=forms.Select(choices=GROUP_CHOICES)
        self.fields['revision'].widget.attrs['size'] = 2
        self.fields['abstract'].widget.attrs['cols'] = 72
        # setup special fields
        if self.instance:
            if self.instance.replaced_by:
                self.fields['replaced_by'].initial = self.instance.replaced_by.filename
            if '.txt' in self.instance.file_type:
                self.fields['file_type_txt'].initial = True
            if '.pdf' in self.instance.file_type:
                self.fields['file_type_pdf'].initial = True
            if '.ps' in self.instance.file_type:
                self.fields['file_type_ps'].initial = True
            if '.xml' in self.instance.file_type:
                self.fields['file_type_xml'].initial = True
            # the database actually contains values of "YES", "NO", "", "-" in this field.
            # only "YES" equals truth
            if self.instance.lc_changes == 'YES':
                self.fields['lc_changes'].initial = True
            else:
                self.fields['lc_changes'].initial = False

    def save(self, force_insert=False, force_update=False, commit=True):
        m = super(EditModelForm, self).save(commit=False)
        if 'replaced_by' in self.changed_data:
            rep = self.cleaned_data.get('replaced_by','')
            if rep:
                id = InternetDraft.objects.get(filename=rep)
                m.replaced_by = id
        if 'lc_changes' in self.changed_data:
            if self.cleaned_data.get('lc_changes',''):
                m.lc_changes = 'YES'
            else:
                m.lc_changes = 'NO'
        # gather file types
        if ('file_type_txt' in self.changed_data) or\
           ('file_type_pdf' in self.changed_data) or\
           ('file_type_ps' in self.changed_data) or\
           ('file_type_xml' in self.changed_data):
            types = []
            if self.cleaned_data.get('file_type_txt',''):
                types.append('.txt')
            if self.cleaned_data.get('file_type_pdf',''):
                types.append('.pdf')
            if self.cleaned_data.get('file_type_ps',''):
                types.append('.ps')
            if self.cleaned_data.get('file_type_xml',''):
                types.append('.xml')
            m.file_type = ','.join(types)     
        if commit:
            m.save()
        return m

    # field must contain filename of existing draft
    def clean_replaced_by(self):
        name = self.cleaned_data.get('replaced_by', '')
        if name and not InternetDraft.objects.filter(filename=name):
            raise forms.ValidationError("ERROR: Draft does not exist") 
        return name
        
    def clean(self):
        super(EditModelForm, self).clean()
        cleaned_data = self.cleaned_data
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
        return cleaned_data
                
class EmailForm(forms.Form):
    # max_lengths come from db limits, cc is not limited
    to = forms.CharField(max_length=255)
    cc = forms.CharField(required=False)
    subject = forms.CharField(max_length=255)
    body = forms.CharField(widget=forms.Textarea())
    
class ExtendForm(forms.Form):
    revision_date = forms.DateField()
    
class ReplaceForm(forms.Form):
    replaced_by = forms.CharField(max_length=100,help_text='Enter the filename of the Draft which replaces this one.')

    def __init__(self, draft, *args, **kwargs):
        self.draft = draft
        super(ReplaceForm, self).__init__(*args, **kwargs)
        
    # field must contain filename of existing draft
    def clean_replaced_by(self):
        name = self.cleaned_data.get('replaced_by', '')
        if name and not InternetDraft.objects.filter(filename=name):
            raise forms.ValidationError("ERROR: Draft does not exist")
        if name == self.draft.filename:
            raise forms.ValidationError("ERROR: A draft can't replace itself")
        return name
        
class BaseRevisionModelForm(forms.ModelForm):
    class Meta:
        model = InternetDraft
        fields = ('title','revision_date','txt_page_count','abstract')

class RevisionFileForm(forms.Form):
    # it appears the file input widget is not stylable via css
    file = DocumentField()
    # we need this hidden field for validation
    # draft = forms.CharField(widget=forms.HiddenInput())
    
class RevisionModelForm(forms.ModelForm):
    # file = DocumentField()
    
    class Meta:
        model = InternetDraft
        fields = ('title','revision_date','txt_page_count','abstract')
    
    # use this method to set attrs which keeps other meta info from model.  
    def __init__(self, *args, **kwargs):
        super(RevisionModelForm, self).__init__(*args, **kwargs)
        self.fields['title'].label='Document Name'
        self.fields['title'].widget=forms.Textarea()
        self.fields['txt_page_count'].label='Number of Pages'
        
    # ensure basename is same as existing 
    '''
    def clean_file(self):
        file = self.cleaned_data.get('file')
        if get_base(file.name) != self.instance.filename:
            raise forms.ValidationError("Basename doesn't match (%s)" % self.instance.filename)
        if int(get_revision(file.name)) != int(self.instance.revision) + 1:
            raise forms.ValidationError("File doesn't match next revision # (%s)" % str(int(self.instance.revision)+1).zfill(2))
        return file
    '''
    
class RevisionForm(forms.Form):
    abstract = forms.CharField(widget=forms.Textarea())
    txt_page_count = forms.IntegerField(label='Number of Pages')
    file = DocumentField()
    draft = forms.CharField(widget=forms.HiddenInput())
    
    # ensure basename is same as existing 
    def clean_file(self):
        file = self.cleaned_data.get('file')
        if get_base(file.name) != self.instance.filename:
            raise forms.ValidationError("Basename doesn't match (%s)" % self.instance.filename)
        return file
        
class RfcForm(forms.ModelForm):
    class Meta:
        model = Rfc
        exclude = ('lc_sent_date','lc_expiration_date','b_sent_date','b_approve_date','intended_status','last_modified_date')
    
    # use this method to set attrs which keeps other meta info from model.  
    def __init__(self, *args, **kwargs):
        super(RfcForm, self).__init__(*args, **kwargs)
        self.fields['area_acronym'].widget.choices = RFC_AREA_CHOICES
        self.fields['group_acronym'].widget.choices = RFC_GROUP_CHOICES
        self.fields['title'].widget = forms.Textarea()
        
class RfcObsoletesForm(forms.Form):
    relation = forms.CharField(widget=forms.Select(choices=RFC_OBS_CHOICES),required=False)
    rfc = forms.IntegerField(required=False)
    
    # ensure that RFC exists
    def clean_rfc(self):
        rfc = self.cleaned_data.get('rfc','')
        if rfc:
            try:
                test = Rfc.objects.get(rfc_number=rfc)
            except Rfc.DoesNotExist:
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
"""
class SearchForm(forms.Form):
    intended_status = forms.CharField(max_length=25,widget=forms.Select(choices=SEARCH_IS_CHOICES),required=False)
    document_name = forms.CharField(max_length=80,label='Document title',required=False)
    group_acronym = forms.CharField(max_length=12,required=False)
    filename = forms.CharField(max_length=80,required=False)
    status = forms.CharField(max_length=25,widget=forms.Select(choices=SEARCH_STATUS_CHOICES),required=False)
    revision_date_start = forms.DateField(required=False)
    revision_date_end = forms.DateField(required=False)
"""
class SubmissionDatesForm(forms.ModelForm):
    class Meta:
        model = IDDates
        fields = ('date','id')
        
class WithdrawForm(forms.Form):
    type = forms.CharField(widget=forms.Select(choices=WITHDRAW_CHOICES),help_text='Select which type of withdraw to perform')
"""   
