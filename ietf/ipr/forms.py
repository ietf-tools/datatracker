import datetime
import email

from django.utils.safestring import mark_safe
from django import forms

from ietf.group.models import Group
from ietf.doc.fields import SearchableDocAliasField
from ietf.ipr.mail import utc_from_string
from ietf.ipr.fields import SearchableIprDisclosuresField
from ietf.ipr.models import (IprDocRel, IprDisclosureBase, HolderIprDisclosure,
    GenericIprDisclosure, ThirdPartyIprDisclosure, NonDocSpecificIprDisclosure,
    IprLicenseTypeName, IprDisclosureStateName)
from ietf.message.models import Message
from ietf.utils.fields import DatepickerDateField

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
    comment = forms.CharField(required=True, widget=forms.Textarea)
    private = forms.BooleanField(label="Private comment", required=False,help_text="If this box is checked the comment will not appear in the disclosure's public history view.")

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
    document = SearchableDocAliasField(label="I-D name/RFC number", required=True, doc_type="draft")

    class Meta:
        model = IprDocRel
        fields = '__all__'
        widgets = {
            'sections': forms.TextInput(),
        }
        help_texts = { 'sections': 'Sections' }

class GenericDisclosureForm(forms.Form):
    """Custom ModelForm-like form to use for new Generic or NonDocSpecific Iprs.
    If patent_info is submitted create a NonDocSpecificIprDisclosure object
    otherwise create a GenericIprDisclosure object."""
    compliant = forms.BooleanField(label="This disclosure complies with RFC 3979", required=False)
    holder_legal_name = forms.CharField(max_length=255)
    notes = forms.CharField(label="Additional notes", max_length=255,widget=forms.Textarea,required=False)
    other_designations = forms.CharField(label="Designations for other contributions", max_length=255,required=False)
    holder_contact_name = forms.CharField(label="Name", max_length=255)
    holder_contact_email = forms.EmailField(label="Email")
    holder_contact_info = forms.CharField(label="Other Info (address, phone, etc.)", max_length=255,widget=forms.Textarea,required=False)
    submitter_name = forms.CharField(max_length=255,required=False)
    submitter_email = forms.EmailField(required=False)
    patent_info = forms.CharField(max_length=255,widget=forms.Textarea, required=False, help_text="Patent, Serial, Publication, Registration, or Application/File number(s), Date(s) granted or applied for, Country, and any additional notes.")
    has_patent_pending = forms.BooleanField(required=False)
    statement = forms.CharField(max_length=255,widget=forms.Textarea,required=False)
    updates = SearchableIprDisclosuresField(required=False, help_text="If this disclosure <strong>updates</strong> other disclosures identify here which ones. Leave this field blank if this disclosure does not update any prior disclosures. <strong>Note</strong>: Updates to IPR disclosures must only be made by authorized representatives of the original submitters. Updates will automatically be forwarded to the current Patent Holder's Contact and to the Submitter of the original IPR disclosure.")
    same_as_ii_above = forms.BooleanField(label="Same as in section II above", required=False)
    
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
    updates = SearchableIprDisclosuresField(required=False, help_text=mark_safe("If this disclosure <strong>updates</strong> other disclosures identify here which ones. Leave this field blank if this disclosure does not update any prior disclosures. Note: Updates to IPR disclosures must only be made by authorized representatives of the original submitters. Updates will automatically be forwarded to the current Patent Holder's Contact and to the Submitter of the original IPR disclosure."))
    same_as_ii_above = forms.BooleanField(required=False)
    
    def __init__(self,*args,**kwargs):
        super(IprDisclosureFormBase, self).__init__(*args,**kwargs)
        self.fields['submitter_name'].required = False
        self.fields['submitter_email'].required = False
        self.fields['compliant'].initial = True
        self.fields['compliant'].label = "This disclosure complies with RFC 3979"
        if "ietfer_name" in self.fields:
            self.fields["ietfer_name"].label = "Name"
        if "ietfer_contact_email" in self.fields:
            self.fields["ietfer_contact_email"].label = "Email"
        if "ietfer_contact_info" in self.fields:
            self.fields["ietfer_contact_info"].label = "Other info"
            self.fields["ietfer_contact_info"].help_text = "Address, phone, etc."
        if "patent_info" in self.fields:
            self.fields["patent_info"].help_text = "Patent, Serial, Publication, Registration, or Application/File number(s), Date(s) granted or applied for, Country, and any additional notes"
        if "licensing" in self.fields:
            self.fields["licensing_comments"].label = "Licensing information, comments, notes, or URL for further information"
        if "submitter_claims_all_terms_disclosed" in self.fields:
            self.fields["submitter_claims_all_terms_disclosed"].label = "The individual submitting this template represents and warrants that all terms and conditions that must be satisfied for implementers of any covered IETF specification to obtain a license have been disclosed in this IPR disclosure statement"
        if "same_as_ii_above" in self.fields:
            self.fields["same_as_ii_above"].label = "Same as in section II above"
    
    class Meta:
        """This will be overridden"""
        model = IprDisclosureBase
        fields = '__all__'
        
    def clean(self):
        super(IprDisclosureFormBase, self).clean()
        cleaned_data = self.cleaned_data
        
        if not self.instance.pk:
            # when entering a new disclosure, if same_as_above not checked require submitted
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
        if self.instance.pk:
            # editing existing disclosure
            self.fields['patent_info'].required = False
            self.fields['holder_contact_name'].required = False
            self.fields['holder_contact_email'].required = False
        else:
            # entering new disclosure
            self.fields['licensing'].queryset = IprLicenseTypeName.objects.exclude(slug='none-selected')
            
    def clean(self):
        super(HolderIprDisclosureForm, self).clean()
        cleaned_data = self.cleaned_data
        if not self.data.get('iprdocrel_set-0-document') and not cleaned_data.get('other_designations'):
            raise forms.ValidationError('You need to specify a contribution in Section IV')
        return cleaned_data

    def save(self, *args, **kwargs):
        obj = super(HolderIprDisclosureForm, self).save(*args,commit=False)
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
    response_due = DatepickerDateField(date_format="yyyy-mm-dd", picker_settings={"autoclose": "1" }, required=False, help_text='The date which a response is due.')
    
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
    
class ThirdPartyIprDisclosureForm(IprDisclosureFormBase):
    class Meta:
        model = ThirdPartyIprDisclosure
        exclude = [ 'by','docs','state','rel' ]

    def clean(self):
        super(ThirdPartyIprDisclosureForm, self).clean()
        cleaned_data = self.cleaned_data
        if not self.data.get('iprdocrel_set-0-document') and not cleaned_data.get('other_designations'):
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
    draft =    forms.CharField(label="Draft name", max_length=128, required=False)
    rfc =      forms.IntegerField(label="RFC number", required=False)
    holder =   forms.CharField(label="Name of patent owner/applicant", max_length=128,required=False)
    patent =   forms.CharField(label="Text in patent information", max_length=128,required=False)
    group =    GroupModelChoiceField(label="Working group",queryset=Group.objects.filter(type='wg').order_by('acronym'),required=False, empty_label="(Select WG)")
    doctitle = forms.CharField(label="Words in document title", max_length=128,required=False)
    iprtitle = forms.CharField(label="Words in IPR disclosure title", max_length=128,required=False)

class StateForm(forms.Form):
    state = forms.ModelChoiceField(queryset=IprDisclosureStateName.objects,label="New State",empty_label=None)
    comment = forms.CharField(required=False, widget=forms.Textarea, help_text="You may add a comment to be included in the disclosure history.")
    private = forms.BooleanField(label="Private comment", required=False, help_text="If this box is checked the comment will not appear in the disclosure's public history view.")
