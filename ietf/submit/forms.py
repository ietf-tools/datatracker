import datetime
from email.utils import parseaddr

from django import forms
from django.conf import settings
from django.db.models import Q
from django.forms.util import ErrorList
from django.forms.fields import email_re
from django.template.loader import render_to_string

from ietf.liaisons.accounts import (can_add_outgoing_liaison, can_add_incoming_liaison,
                                    get_person_for_user, is_ietf_liaison_manager)
from ietf.liaisons.models import LiaisonDetail, Uploads, OutgoingLiaisonApproval, SDOs
from ietf.liaisons.utils import IETFHM
from ietf.liaisons.widgets import (FromWidget, ReadOnlyWidget, ButtonWidget,
                                   ShowAttachmentsWidget, RelatedLiaisonWidget)


from ietf.submit.models import IdSubmitDateConfig
from ietf.submit.parsers.plain_parser import PlainParser
from ietf.submit.parsers.pdf_parser import PDFParser
from ietf.submit.parsers.ps_parser import PSParser
from ietf.submit.parsers.xml_parser import XMLParser


CUTOFF_HOUR = 17


class UploadForm(forms.Form):

    txt = forms.FileField(label=u'.txt format', required=True)
    xml = forms.FileField(label=u'.xml format', required=False)
    pdf = forms.FileField(label=u'.pdf format', required=False)
    ps = forms.FileField(label=u'.ps format', required=False)

    fieldsets = [('Upload a draft', ('txt', 'xml', 'pdf', 'ps'))]

    class Media:
        css = {'all': ("/css/liaisons.css", )}

    def __init__(self, *args, **kwargs):
        super(UploadForm, self).__init__(*args, **kwargs)
        self.in_first_cut_off = False
        self.shutdown = False
        self.read_dates()

    def read_dates(self):
        now = datetime.datetime.now()
        first_cut_off = IdSubmitDateConfig.get_first_cut_off()
        second_cut_off = IdSubmitDateConfig.get_second_cut_off()
        ietf_monday = IdSubmitDateConfig.get_ietf_monday()
        processed_ids_date = IdSubmitDateConfig.get_processed_ids_date()
        monday_after_ietf = IdSubmitDateConfig.get_monday_after_ietf()
        list_aproved_date = IdSubmitDateConfig.get_list_aproved_date()

        if now.date() >= first_cut_off and now.date() < second_cut_off:  # We are in the first_cut_off
            if now.date() == first_cut_off and now.hour < CUTOFF_HOUR:
                self.cutoff_warning = 'The pre-meeting cutoff date for new documents (i.e., version -00 Internet-Drafts) is %s at 5 PM (PT). You will not be able to submit a new document after this time until %s, at midnight' % (first_cut_off, ietf_monday)
            else:  # No 00 version allowed
                self.cutoff_warning = 'The pre-meeting cutoff date for new documents (i.e., version -00 Internet-Drafts) was %s at 5 PM (PT). You will not be able to submit a new document until %s, at midnight.<br>You can still submit a version -01 or higher Internet-Draft until 5 PM (PT), %s' % (first_cut_off, ietf_monday, second_cut_off)
                self.in_first_cut_off = True
        elif now.date() >= second_cut_off and now.date() < ietf_monday:
            if now.date() == second_cut_off and now.hour < CUTOFF_HOUR:  # We are in the first_cut_off yet
                self.cutoff_warning = 'The pre-meeting cutoff date for new documents (i.e., version -00 Internet-Drafts) was %s at 5 PM (PT). You will not be able to submit a new document until %s, at midnight.<br>The I-D submission tool will be shut down at 5 PM (PT) today, and reopened at midnight (PT), %s' % (first_cut_off, ietf_monday, ietf_monday)
                self.in_first_cut_off = True
            else:  # Completely shut down of the tool
                self.cutoff_warning = 'The cut off time for the I-D submission was 5 PM (PT), %s.<br>The I-D submission tool will be reopened at midnight, %s' % (second_cut_off, ietf_monday)
                self.shutdown = True

    def __unicode__(self):
        return self.as_div()

    def as_div(self):
        return render_to_string('submit/submitform.html', {'form': self})

    def get_fieldsets(self):
        if not self.fieldsets:
            yield dict(name=None, fields=self)
        else:
            for fieldset, fields in self.fieldsets:
                fieldset_dict = dict(name=fieldset, fields=[])
                for field_name in fields:
                    if field_name in self.fields.keyOrder:
                        fieldset_dict['fields'].append(self[field_name])
                    if not fieldset_dict['fields']:
                        # if there is no fields in this fieldset, we continue to next fieldset
                        continue
                yield fieldset_dict

    def clean_txt(self):
        parsed_info = PlainParser(self.cleaned_data['txt']).parse_critical()
        if parsed_info.errors:
            raise forms.ValidationError(parsed_info.errors)

    def clean_pdf(self):
        parsed_info = PDFParser(self.cleaned_data['pdf']).parse_critical()
        if parsed_info.errors:
            raise forms.ValidationError(parsed_info.errors)

    def clean_ps(self):
        parsed_info = PSParser(self.cleaned_data['ps']).parse_critical()
        if parsed_info.errors:
            raise forms.ValidationError(parsed_info.errors)

    def clean_xml(self):
        parsed_info = XMLParser(self.cleaned_data['xml']).parse_critical()
        if parsed_info.errors:
            raise forms.ValidationError(parsed_info.errors)

    def clean(self):
        if self.shutdown:
            raise forms.ValidationError('The tool is shut down')
        return super(UploadForm, self).clean()
