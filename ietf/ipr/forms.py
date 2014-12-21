import datetime
import email

from django import forms

from ietf.group.models import Group
from ietf.ipr.mail import utc_from_string
from ietf.ipr.fields import (AutocompletedIprDisclosuresField, AutocompletedDraftField,
    AutocompletedRfcField)
from ietf.ipr.models import (IprDocRel, IprDisclosureBase, HolderIprDisclosure,
    GenericIprDisclosure, ThirdPartyIprDisclosure, NonDocSpecificIprDisclosure,
    IprLicenseTypeName, IprDisclosureStateName)
from ietf.message.models import Message

# ----------------------------------------------------------------
# Globals
# ----------------------------------------------------------------
STATE_CHOICES = [ (x.slug, x.name) for x in IprDisclosureStateName.objects.all() ]
STATE_CHOICES.insert(0,('all','All States'))

# ----------------------------------------------------------------
# Base Classes
# ----------------------------------------------------------------
class CustomModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.desc

class GroupModelChoiceField(forms.ModelChoiceField):
    '''Custom ModelChoiceField that displays group acronyms as choices.'''
    def label_from_instance(self, obj):
        return obj.acronym

class MessageModelChoiceField(forms.ModelChoiceField):
    '''Custom ModelChoiceField that displays messages.'''
    def label_from_instance(self, obj):
        date = obj.time.strftime("%Y-%m-%d")
        if len(obj.subject) > 45:
            subject = obj.subject[:43] + '....'
        else:
            subject = obj.subject
        return '{} - {}'.format(date,subject)

# ----------------------------------------------------------------
# Forms
# ----------------------------------------------------------------
class AddCommentForm(forms.Form):
    private = forms.BooleanField(required=False,help_text="If this box is checked the comment will not appear in the disclosure's public history view.")
    comment = forms.CharField(required=True, widget=forms.Textarea)

class AddEmailForm(forms.Form):
    direction = forms.ChoiceField(choices=(("incoming", "Incoming"), ("outgoing", "Outgoing")),
        widget=forms.RadioSelect)
    in_reply_to = MessageModelChoiceField(queryset=Message.objects,label="In Reply To",required=False)
    message = forms.CharField(required=True, widget=forms.Textarea)

    def __init__(self, *args, **kwargs):
        self.ipr = kwargs.pop('ipr', None)
        super(AddEmailForm, self).__init__(*args, **kwargs)

        if self.ipr:
            self.fields['in_reply_to'].queryset = Message.objects.filter(msgevents__disclosure__id=self.ipr.pk)

    def clean_message(self):
        '''Returns a ietf.message.models.Message object'''
        text = self.cleaned_data['message']
        message = email.message_from_string(text)
        for field in ('to','from','subject','date'):
            if not message[field]:
                raise forms.ValidationError('Error parsing email: {} field not found.'.format(field))
        date = utc_from_string(message['date'])
        if not isinstance(date,datetime.datetime):
            raise forms.ValidationError('Error parsing email date field')
        return message
        
    def clean(self):
        if any(self.errors):
            return self.cleaned_data
        super(AddEmailForm, self).clean()
        in_reply_to = self.cleaned_data['in_reply_to']
        message = self.cleaned_data['message']
        direction = self.cleaned_data['direction']
        if in_reply_to:
            if direction != 'incoming':
                raise forms.ValidationError('Only incoming messages can have In Reply To selected')
            date = utc_from_string(message['date'])
            if date < in_reply_to.time:
                raise forms.ValidationError('The incoming message must have a date later than the message it is replying to')
        
        return self.cleaned_data

class DraftForm(forms.ModelForm):
    document = AutocompletedDraftField(required=False)
    
    class Meta:
        model = IprDocRel
        widgets = {
            'sections': forms.TextInput(),
        }
        help_texts = { 'sections': 'Sections' }

class GenericDisclosureForm(forms.Form):
    """Custom ModelForm-like form to use for new Generic or NonDocSpecific Iprs.
    If patent_info is submitted create a NonDocSpecificIprDisclosure object
    otherwise create a GenericIprDisclosure object."""
    compliant = forms.BooleanField(required=False)
    holder_legal_name = forms.CharField(max_length=255)
    notes = forms.CharField(max_length=255,widget=forms.Textarea,required=False)
    other_designations = forms.CharField(max_length=255,required=False)
    holder_contact_name = forms.CharField(max_length=255)
    holder_contact_email = forms.EmailField()
    holder_contact_info = forms.CharField(max_length=255,widget=forms.Textarea,required=False)
    submitter_name = forms.CharField(max_length=255,required=False)
    submitter_email = forms.EmailField(required=False)
    patent_info = forms.CharField(max_length=255,widget=forms.Textarea,required=False)
    has_patent_pending = forms.BooleanField(required=False)
    statement = forms.CharField(max_length=255,widget=forms.Textarea,required=False)
    updates = AutocompletedIprDisclosuresField(required=False)
    same_as_ii_above = forms.BooleanField(required=False)
    
    def __init__(self,*args,**kwargs):
        super(GenericDisclosureForm, self).__init__(*args,**kwargs)
        self.fields['compliant'].initial = True
        
    def clean(self):
        super(GenericDisclosureForm, self).clean()
        cleaned_data = self.cleaned_data
        
        # if same_as_above not checked require submitted
        if not self.cleaned_data.get('same_as_ii_above'):
            if not ( self.cleaned_data.get('submitter_name') and self.cleaned_data.get('submitter_email') ):
                raise forms.ValidationError('Submitter information must be provided in section VII')
        
        return cleaned_data
        
    def save(self, *args, **kwargs):
        nargs = self.cleaned_data.copy()
        same_as_ii_above = nargs.get('same_as_ii_above')
        del nargs['same_as_ii_above']
        
        if self.cleaned_data.get('patent_info'):
            obj = NonDocSpecificIprDisclosure(**nargs)
        else:
            del nargs['patent_info']
            del nargs['has_patent_pending']
            obj = GenericIprDisclosure(**nargs)
        
        if same_as_ii_above == True:
            obj.submitter_name = obj.holder_contact_name
            obj.submitter_email = obj.holder_contact_email
            
        if kwargs.get('commit',True):
            obj.save()
        
        return obj

class IprDisclosureFormBase(forms.ModelForm):
    """Base form for Holder and ThirdParty disclosures"""
    updates = AutocompletedIprDisclosuresField(required=False)
    same_as_ii_above = forms.BooleanField(required=False)
    
    def __init__(self,*args,**kwargs):
        super(IprDisclosureFormBase, self).__init__(*args,**kwargs)
        self.fields['submitter_name'].required = False
        self.fields['submitter_email'].required = False
        self.fields['compliant'].initial = True
    
    class Meta:
        """This will be overridden"""
        model = IprDisclosureBase
        
    def clean(self):
        super(IprDisclosureFormBase, self).clean()
        cleaned_data = self.cleaned_data
        
        # if same_as_above not checked require submitted
        if not self.cleaned_data.get('same_as_ii_above'):
            if not ( self.cleaned_data.get('submitter_name') and self.cleaned_data.get('submitter_email') ):
                raise forms.ValidationError('Submitter information must be provided in section VII')
        
        return cleaned_data

class HolderIprDisclosureForm(IprDisclosureFormBase):
    licensing = CustomModelChoiceField(IprLicenseTypeName.objects.all(),
        widget=forms.RadioSelect,empty_label=None)

    class Meta:
        model = HolderIprDisclosure
        exclude = [ 'by','docs','state','rel' ]
        
    def __init__(self, *args, **kwargs):
        super(HolderIprDisclosureForm, self).__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['licensing'].queryset = IprLicenseTypeName.objects.exclude(slug='none-selected')
            
    def clean(self):
        super(HolderIprDisclosureForm, self).clean()
        cleaned_data = self.cleaned_data
        if not self.data.get('draft-0-document') and not self.data.get('rfc-0-document') and not cleaned_data.get('other_designations'):
            raise forms.ValidationError('You need to specify a contribution in Section IV')
        return cleaned_data

    def save(self, *args, **kwargs):
        obj = super(IprDisclosureFormBase, self).save(*args,commit=False)
        if self.cleaned_data.get('same_as_ii_above') == True:
            obj.submitter_name = obj.holder_contact_name
            obj.submitter_email = obj.holder_contact_email
        if kwargs.get('commit',True):
            obj.save()
        return obj
        
class GenericIprDisclosureForm(IprDisclosureFormBase):
    """Use for editing a GenericIprDisclosure"""
    class Meta:
        model = GenericIprDisclosure
        exclude = [ 'by','docs','state','rel' ]
        
class MessageModelForm(forms.ModelForm):
    response_due = forms.DateField(required=False,help_text='The date which a response is due')
    
    class Meta:
        model = Message
        fields = ['to','frm','cc','bcc','reply_to','subject','body']
        exclude = ['time','by','content_type','related_groups','related_docs']
    
    def __init__(self, *args, **kwargs):
        super(MessageModelForm, self).__init__(*args, **kwargs)
        self.fields['frm'].label='From'
        self.fields['frm'].widget.attrs['readonly'] = True
        self.fields['reply_to'].widget.attrs['readonly'] = True

class NonDocSpecificIprDisclosureForm(IprDisclosureFormBase):
    class Meta:
        model = NonDocSpecificIprDisclosure
        exclude = [ 'by','docs','state','rel' ]
        
class NotifyForm(forms.Form):
    type = forms.CharField(widget=forms.HiddenInput)
    text = forms.CharField(widget=forms.Textarea)
    
class RfcForm(DraftForm):
    document = AutocompletedRfcField(required=False)
    
    class Meta(DraftForm.Meta):
        exclude = ('revisions',)

class ThirdPartyIprDisclosureForm(IprDisclosureFormBase):
    class Meta:
        model = ThirdPartyIprDisclosure
        exclude = [ 'by','docs','state','rel' ]

    def clean(self):
        super(ThirdPartyIprDisclosureForm, self).clean()
        cleaned_data = self.cleaned_data
        if not self.data.get('draft-0-document') and not self.data.get('rfc-0-document') and not cleaned_data.get('other_designations'):
            raise forms.ValidationError('You need to specify a contribution in Section III')
        return cleaned_data
    
    def save(self, *args, **kwargs):
        obj = super(ThirdPartyIprDisclosureForm, self).save(*args,commit=False)
        if self.cleaned_data.get('same_as_ii_above') == True:
            obj.submitter_name = obj.ietfer_name
            obj.submitter_email = obj.ietfer_contact_email
        if kwargs.get('commit',True):
            obj.save()
        
        return obj
        
class SearchForm(forms.Form):
    state =    forms.MultipleChoiceField(choices=STATE_CHOICES,widget=forms.CheckboxSelectMultiple,required=False)
    draft =    forms.CharField(max_length=128,required=False)
    rfc =      forms.IntegerField(required=False)
    holder =   forms.CharField(max_length=128,required=False)
    patent =   forms.CharField(max_length=128,required=False)
    group =    GroupModelChoiceField(label="Working group name",queryset=Group.objects.filter(type='wg').order_by('acronym'),required=False)
    doctitle = forms.CharField(max_length=128,required=False)
    iprtitle = forms.CharField(max_length=128,required=False)

class StateForm(forms.Form):
    state = forms.ModelChoiceField(queryset=IprDisclosureStateName.objects,label="New State",empty_label=None)
    private = forms.BooleanField(required=False,help_text="If this box is checked the comment will not appear in the disclosure's public history view.")
    comment = forms.CharField(required=False, widget=forms.Textarea)
