import os

from django import forms
from django.conf import settings
from django.template.defaultfilters import filesizeformat

from ietf.doc.models import Document
from ietf.name.models import DocTypeName
from ietf.meeting.models import Session


# ---------------------------------------------
# Globals
# ---------------------------------------------

VALID_SLIDE_EXTENSIONS = ('.doc','.docx','.pdf','.ppt','.pptx','.txt','.zip')
VALID_MINUTES_EXTENSIONS = ('.txt','.html','.htm','.pdf')
VALID_AGENDA_EXTENSIONS = ('.txt','.html','.htm')
VALID_BLUESHEET_EXTENSIONS = ('.pdf','.jpg','.jpeg')

#----------------------------------------------------------
# Forms
#----------------------------------------------------------

class EditSlideForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ('title',)

class RecordingForm(forms.Form):
    external_url = forms.URLField(label='Url')
    session = forms.ModelChoiceField(queryset=Session.objects,empty_label='')
    
    def __init__(self, *args, **kwargs):
        self.meeting = kwargs.pop('meeting')
        super(RecordingForm, self).__init__(*args,**kwargs)
        self.fields['session'].queryset = Session.objects.filter(meeting=self.meeting,
            type__in=('session','plenary','other'),status='sched').order_by('group__acronym')

class RecordingEditForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['external_url']
        
    def __init__(self, *args, **kwargs):
        super(RecordingEditForm, self).__init__(*args, **kwargs)
        self.fields['external_url'].label='Url'

class ReplaceSlideForm(forms.ModelForm):
    file = forms.FileField(label='Select File')
    
    class Meta:
        model = Document
        fields = ('title',)
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        ext = os.path.splitext(file.name)[1].lower()
        if ext not in VALID_SLIDE_EXTENSIONS:
            raise forms.ValidationError('Only these file types supported for presentation slides: %s' % ','.join(VALID_SLIDE_EXTENSIONS))
        if file._size > settings.SECR_MAX_UPLOAD_SIZE:
            raise forms.ValidationError('Please keep filesize under %s. Current filesize %s' % (filesizeformat(settings.SECR_MAX_UPLOAD_SIZE), filesizeformat(file._size)))
        return file

class UnifiedUploadForm(forms.Form):
    acronym = forms.CharField(widget=forms.HiddenInput())
    meeting_id = forms.CharField(widget=forms.HiddenInput())
    material_type = forms.ModelChoiceField(queryset=DocTypeName.objects.filter(slug__in=('minutes','agenda','slides','bluesheets')),empty_label=None)
    slide_name = forms.CharField(label='Name of Presentation',max_length=255,required=False,help_text="For presentations only")
    file = forms.FileField(label='Select File',help_text='<div id="id_file_help">Note 1: You can only upload a presentation file in txt, pdf, doc, or ppt/pptx. System will not accept presentation files in any other format.<br><br>Note 2: All uploaded files will be available to the public immediately on the Preliminary Page. However, for the Proceedings, ppt/pptx files will be converted to html format and doc files will be converted to pdf format manually by the Secretariat staff.</div>')
    
    def clean_file(self):
        file = self.cleaned_data['file']
        if file._size > settings.SECR_MAX_UPLOAD_SIZE:
            raise forms.ValidationError('Please keep filesize under %s. Current filesize %s' % (filesizeformat(settings.SECR_MAX_UPLOAD_SIZE), filesizeformat(file._size)))
        return file
        
    def clean(self):
        super(UnifiedUploadForm, self).clean()
        # if an invalid file type is supplied no file attribute will exist
        if self.errors:
            return self.cleaned_data
        cleaned_data = self.cleaned_data
        material_type = cleaned_data['material_type']
        slide_name = cleaned_data['slide_name']
        file = cleaned_data['file']
        ext = os.path.splitext(file.name)[1].lower()

        if material_type.slug == 'slides' and not slide_name:
            raise forms.ValidationError('ERROR: Name of Presentaion cannot be blank')
        
        # only supporting PDFs per Alexa 04-05-2011
        #if material_type == 1 and not file_ext[1] == '.pdf': 
        #        raise forms.ValidationError('Presentations must be a PDF file')
       
        # validate file extensions based on material type (slides,agenda,minutes,bluesheets)
        # valid extensions per online documentation: meeting-materials.html
        # 09-14-11 added ppt, pdf per Alexa
        # 04-19-12 txt/html for agenda, +pdf for minutes per Russ
        if material_type.slug == 'slides' and ext not in VALID_SLIDE_EXTENSIONS:
            raise forms.ValidationError('Only these file types supported for presentation slides: %s' % ','.join(VALID_SLIDE_EXTENSIONS))
        if material_type.slug == 'agenda' and ext not in VALID_AGENDA_EXTENSIONS:
            raise forms.ValidationError('Only these file types supported for agendas: %s' % ','.join(VALID_AGENDA_EXTENSIONS))
        if material_type.slug == 'minutes' and ext not in VALID_MINUTES_EXTENSIONS:
            raise forms.ValidationError('Only these file types supported for minutes: %s' % ','.join(VALID_MINUTES_EXTENSIONS))
        if material_type.slug == 'bluesheets' and ext not in VALID_BLUESHEET_EXTENSIONS:
            raise forms.ValidationError('Only these file types supported for bluesheets: %s' % ','.join(VALID_BLUESHEET_EXTENSIONS))
            
        return cleaned_data

        
