# Copyright The IETF Trust 2014-2023, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import email


from django import forms
from django.core.validators import RegexValidator
from django.utils.safestring import mark_safe
from django.utils.encoding import force_str

import debug                            # pyflakes:ignore

from ietf.group.models import Group
from ietf.doc.fields import SearchableDocumentField
from ietf.ipr.mail import utc_from_string
from ietf.ipr.fields import SearchableIprDisclosuresField
from ietf.ipr.models import (IprDocRel, IprDisclosureBase, HolderIprDisclosure,
    GenericIprDisclosure, ThirdPartyIprDisclosure, NonDocSpecificIprDisclosure,
    IprLicenseTypeName, IprDisclosureStateName)
from ietf.message.models import Message
from ietf.utils.fields import DatepickerDateField
from ietf.utils.text import dict_to_text

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
    comment = forms.CharField(required=True, widget=forms.Textarea, strip=False)
    private = forms.BooleanField(label="Private comment", required=False,help_text="If this box is checked the comment will not appear in the disclosure's public history view.")

class AddEmailForm(forms.Form):
    direction = forms.ChoiceField(choices=(("incoming", "Incoming"), ("outgoing", "Outgoing")),
        widget=forms.RadioSelect)
    in_reply_to = MessageModelChoiceField(queryset=Message.objects,label="In Reply To",required=False)
    message = forms.CharField(required=True, widget=forms.Textarea, strip=False)

    def __init__(self, *args, **kwargs):
        self.ipr = kwargs.pop('ipr', None)
        super(AddEmailForm, self).__init__(*args, **kwargs)

        if self.ipr:
            self.fields['in_reply_to'].queryset = Message.objects.filter(msgevents__disclosure__id=self.ipr.pk)

    def clean_message(self):
        '''Returns a ietf.message.models.Message object'''
        text = self.cleaned_data['message']
        message = email.message_from_string(force_str(text))
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
    document = SearchableDocumentField(label="I-D name/RFC number", required=True, doc_type="all")

    class Meta:
        model = IprDocRel
        fields = '__all__'
        widgets = {
            'sections': forms.TextInput(),
        }
        help_texts = { 'sections': 'Sections' }

    def clean(self):
        cleaned_data = super().clean()
        revisions = cleaned_data.get("revisions")
        document = cleaned_data.get("document")
        if not document:
            self.add_error("document", "Identifying the Internet-Draft or RFC for this disclosure is required.")
        elif not document.name.startswith("rfc"):
            if revisions is None or revisions.strip() == "":
                self.add_error("revisions", "Revisions of this Internet-Draft for which this disclosure is relevant must be specified.")
        return cleaned_data

patent_number_help_text = "Enter one or more comma-separated patent publication or application numbers as two-letter country code and serial number, e.g.: US62/123456 or WO2017123456. Do not include thousands-separator commas in serial numbers.  It is preferable to use individual disclosures for each patent, even if this field permits multiple patents to be listed, in order to get inventor, title, and date information below correct." 
validate_patent_number = RegexValidator(
                                    regex=(r"^("
                                             r"([A-Z][A-Z] *\d\d/\d{6}"
                                             r"|[A-Z][A-Z] *\d{6,12}([A-Z]\d?)?"
                                             r"|[A-Z][A-Z] *\d{4}(\w{1,2}\d{5,7})?"
                                             r"|[A-Z][A-Z] *\d{15}"
                                             r"|[A-Z][A-Z][A-Z] *\d{1,5}/\d{4}" 
                                             r"|[A-Z][A-Z] *\d{1,4}/\d{1,4}" 
                                             r"|PCT/[A-Z][A-Z]*\d{2}/\d{5}" # WO application, old
                                             r"|PCT/[A-Z][A-Z]*\d{4}/\d{6}" # WO application, new
                                             r")[, ]*)+$"),
                                    message=patent_number_help_text)



"""
Patent application number formats by country

Cc Country	Format example                                  Regex comment
-- ---------    --------------                                  -------------
AT AUSTRIA	A 123/2012
AU AUSTRALIA	2011901234
BA BOSNIA AND HERZEGOVINA	BAP 01 898
BE BELGIUM	2010/0912
BG BULGARIA	10110685 A
BR BRAZIL	302012000001
BY BELARUS	a 20120001
CA CANADA	2000000
CN CHINA	200820033898.2
CR COSTA RICA	2012-0145
CZ CZECH REPUBLIC	PV 2011-772
DE GERMANY	10 2004 000 001.7
EA EURASIAN PATENT OFFICE	201270271
EE ESTONIA	P201200001
EM OHIM	EM500000001104306
EP EUROPEAN PATENT OFFICE	12001234.9
ES SPAIN	P200900623                                      [P0350]200900623
FI FINLAND	20120001
GB UNITED KINGDOM	8912345.1
HR CROATIA	P20110001A
IE IRELAND	2011/0123
IL ISRAEL	195580
IT ITALY	RM2012A000123
JP JAPAN	2012123456
KR REPUBLIC OF KOREA	10-2012-0123456
LT LITHUANIA	2012 001
MD REPUBLIC OF MOLDOVA	a 2012 0001
PL POLAND	P.023456
RO ROMANIA	a 2000 00023
RS SERBIA	P-2010/0044
RU RUSSIAN FEDERATION	2006100001
SA SAUDI ARABIA	108290771
SE SWEDEN	1201234-0
SK SLOVAKIA	PP 50010-2011                                   (PP|PV) 50010-2011
UA UKRAINE	a 2012 00001
US UNITED STATES OF AMERICA	09/123,456
WO World Intellectual Property Organization	PCT/IB2012/050001

"""


def validate_string(s, letter_min, digit_min, space_min, message):
    letter_count = 0
    space_count = 0
    digit_count = 0
    s = s.strip()
    for c in s:
        if c.isalpha():
            letter_count += 1
        if c.isspace():
            space_count += 1
    if not (letter_count >= letter_min and digit_count >= digit_min and space_count >= space_min):
        raise forms.ValidationError(message)

def validate_name(name):
    return validate_string(name, letter_min=3, space_min=1, digit_min=0,
        message="This doesn't look like a name.  Please enter the actual inventor name.")

def validate_title(title):
    return validate_string(title, letter_min=15, space_min=2, digit_min=0,
        message="This doesn't look like a patent title.  Please enter the actual patent title.")

class GenericDisclosureForm(forms.Form):
    """Custom ModelForm-like form to use for new Generic or NonDocSpecific Iprs.
    If patent_info is submitted create a NonDocSpecificIprDisclosure object
    otherwise create a GenericIprDisclosure object."""
    compliant = forms.BooleanField(label="This disclosure complies with RFC 3979", required=False)
    holder_legal_name = forms.CharField(max_length=255)
    notes = forms.CharField(label="Additional notes", max_length=4096,widget=forms.Textarea,required=False, strip=False)
    other_designations = forms.CharField(label="Designations for other contributions", max_length=255,required=False)
    holder_contact_name = forms.CharField(label="Name", max_length=255)
    holder_contact_email = forms.EmailField(label="Email")
    holder_contact_info = forms.CharField(label="Other Info (address, phone, etc.)", max_length=255,widget=forms.Textarea,required=False, strip=False)
    submitter_name = forms.CharField(max_length=255,required=False)
    submitter_email = forms.EmailField(required=False)
    #patent_info = forms.CharField(max_length=255,widget=forms.Textarea, required=False, help_text="Patent, Serial, Publication, Registration, or Application/File number(s), Date(s) granted or applied for, Country, and any additional notes.", strip=False)
    patent_number = forms.CharField(max_length=127, required=False, validators=[ validate_patent_number ],
        help_text = patent_number_help_text)
    patent_inventor =  forms.CharField(max_length=63, required=False, validators=[ validate_name ], help_text="Inventor name")
    patent_title =  forms.CharField(max_length=255, required=False, validators=[ validate_title ], help_text="Title of invention")
    patent_date =  DatepickerDateField(date_format="yyyy-mm-dd", required=False, help_text="Date granted or applied for")
    patent_notes =  forms.CharField(max_length=1024, required=False, widget=forms.Textarea)

    has_patent_pending = forms.BooleanField(required=False)
    statement = forms.CharField(max_length=2000,widget=forms.Textarea,required=False, strip=False)
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

        patent_fields = [ 'patent_'+k for k in ['number', 'inventor', 'title', 'date', ] ]
        patent_values = [ cleaned_data.get(k) for k in patent_fields ]
        if any(patent_values) and not all(patent_values):
            for k in patent_fields:
                if not cleaned_data.get(k):
                    self.add_error(k, "This field is required if you are filing a patent-specific disclosure.")
            raise forms.ValidationError("A general IPR disclosure cannot have any patent-specific information, "
                                        "but a patent-specific disclosure must provide full patent information.")

        patent_fields += ['patent_notes']
        patent_info = dict([ (k.replace('patent_','').capitalize(), cleaned_data.get(k)) for k in patent_fields if cleaned_data.get(k) ] )
        cleaned_data['patent_info'] = dict_to_text(patent_info).strip()
        cleaned_data['patent_fields'] = patent_fields

        return cleaned_data
        
    def save(self, *args, **kwargs):
        nargs = self.cleaned_data.copy()
        same_as_ii_above = nargs.get('same_as_ii_above')
        del nargs['same_as_ii_above']
        
        for k in self.cleaned_data['patent_fields'] + ['patent_fields',]:
            del nargs[k]

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
    patent_number = forms.CharField(max_length=127, required=True, validators=[ validate_patent_number ],
        help_text = patent_number_help_text)
    patent_inventor =  forms.CharField(max_length=63, required=True, validators=[ validate_name ], help_text="Inventor name")
    patent_title =  forms.CharField(max_length=255, required=True, validators=[ validate_title ], help_text="Title of invention")
    patent_date =  DatepickerDateField(date_format="yyyy-mm-dd", required=True, help_text="Date granted or applied for")
    patent_notes =  forms.CharField(max_length=4096, required=False, widget=forms.Textarea)
    
    def __init__(self,*args,**kwargs):
        super(IprDisclosureFormBase, self).__init__(*args,**kwargs)
        self.fields['submitter_name'].required = False
        self.fields['submitter_email'].required = False
        self.fields['compliant'].initial = True
        self.fields['compliant'].label = "This disclosure complies with RFC 3979"
        patent_fields = [ 'patent_'+k for k in ['number', 'inventor', 'title', 'date', ] ]
        if "ietfer_name" in self.fields:
            self.fields["ietfer_name"].label = "Name"
        if "ietfer_contact_email" in self.fields:
            self.fields["ietfer_contact_email"].label = "Email"
        if "ietfer_contact_info" in self.fields:
            self.fields["ietfer_contact_info"].label = "Other info"
            self.fields["ietfer_contact_info"].help_text = "Address, phone, etc."
        if "patent_info" in self.fields:
            self.fields['patent_info'].required = False
        else:
            for f in patent_fields:
                del self.fields[f]
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
        
        patent_fields = [ 'patent_'+k for k in ['number', 'inventor', 'title', 'date', 'notes'] ]

        patent_info = dict([ (k.replace('patent_','').capitalize(), cleaned_data.get(k)) for k in patent_fields if cleaned_data.get(k) ] )
        cleaned_data['patent_info'] = dict_to_text(patent_info).strip()
        cleaned_data['patent_fields'] = patent_fields

        return cleaned_data


class HolderIprDisclosureForm(IprDisclosureFormBase):
    is_blanket_disclosure = forms.BooleanField(
        label=mark_safe(
            'This is a blanket IPR disclosure '
            '(see Section 5.4.3 of <a href="https://www.ietf.org/rfc/rfc8179.txt">RFC 8179</a>)'
        ),
        help_text="In satisfaction of its disclosure obligations, Patent Holder commits to license all of "
                  "IPR (as defined in RFC 8179) that would have required disclosure under RFC 8179 on a "
                  "royalty-free (and otherwise reasonable and non-discriminatory) basis. Patent Holder "
                  "confirms that all other terms and conditions are described in this IPR disclosure.",
        required=False,
    )
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
        
        if self.data.get("is_blanket_disclosure", False):
            # for a blanket disclosure, patent details are not required
            self.fields["patent_number"].required = False
            self.fields["patent_inventor"].required = False
            self.fields["patent_title"].required = False
            self.fields["patent_date"].required = False
            # n.b., self.fields["patent_notes"] is never required

            
    def clean(self):
        cleaned_data = super(HolderIprDisclosureForm, self).clean()
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
    text = forms.CharField(widget=forms.Textarea, strip=False)
    
class ThirdPartyIprDisclosureForm(IprDisclosureFormBase):
    class Meta:
        model = ThirdPartyIprDisclosure
        exclude = [ 'by','docs','state','rel' ]

    def clean(self):
        cleaned_data = super(ThirdPartyIprDisclosureForm, self).clean()
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
    state =    forms.MultipleChoiceField(choices=[], widget=forms.CheckboxSelectMultiple,required=False)
    draft =    forms.CharField(label="Internet-Draft name", max_length=128, required=False)
    rfc =      forms.IntegerField(label="RFC number", required=False)
    holder =   forms.CharField(label="Name of patent owner/applicant", max_length=128,required=False)
    patent =   forms.CharField(label="Text in patent information", max_length=128,required=False)
    group =    GroupModelChoiceField(label="Working group",queryset=Group.objects.filter(type='wg').order_by('acronym'),required=False, empty_label="(Select WG)")
    doctitle = forms.CharField(label="Words in document title", max_length=128,required=False)
    iprtitle = forms.CharField(label="Words in IPR disclosure title", max_length=128,required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['state'].choices = [('all','All States')] + [(n.pk, n.name) for n in IprDisclosureStateName.objects.all()]

class StateForm(forms.Form):
    state = forms.ModelChoiceField(queryset=IprDisclosureStateName.objects,label="New State",empty_label=None)
    comment = forms.CharField(required=False, widget=forms.Textarea, help_text="You may add a comment to be included in the disclosure history.", strip=False)
    private = forms.BooleanField(label="Private comment", required=False, help_text="If this box is checked the comment will not appear in the disclosure's public history view.")
