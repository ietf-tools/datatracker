import os
import subprocess
import datetime

from django import forms
from django.conf import settings
from django.template.loader import render_to_string

from ietf.proceedings.models import Meeting
from ietf.submit.models import IdSubmissionDetail
from ietf.submit.parsers.pdf_parser import PDFParser
from ietf.submit.parsers.plain_parser import PlainParser
from ietf.submit.parsers.ps_parser import PSParser
from ietf.submit.parsers.xml_parser import XMLParser
from ietf.utils.draft import Draft


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
        self.idnits_message = None
        self.shutdown = False
        self.draft = None
        self.read_dates()

    def read_dates(self):
        now = datetime.datetime.now()
        first_cut_off = Meeting.get_first_cut_off()
        second_cut_off = Meeting.get_second_cut_off()
        ietf_monday = Meeting.get_ietf_monday()

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
        txt_file = self.cleaned_data['txt']
        if not txt_file:
            return txt_file
        parsed_info = PlainParser(txt_file).critical_parse()
        if parsed_info.errors:
            raise forms.ValidationError(parsed_info.errors)
        return txt_file

    def clean_pdf(self):
        pdf_file = self.cleaned_data['pdf']
        if not pdf_file: 
            return pdf_file
        parsed_info = PDFParser(pdf_file).critical_parse()
        if parsed_info.errors:
            raise forms.ValidationError(parsed_info.errors)
        return pdf_file

    def clean_ps(self):
        ps_file = self.cleaned_data['ps']
        if not ps_file: 
            return ps_file
        parsed_info = PSParser(ps_file).critical_parse()
        if parsed_info.errors:
            raise forms.ValidationError(parsed_info.errors)
        return ps_file

    def clean_xml(self):
        xml_file = self.cleaned_data['xml']
        if not xml_file: 
            return xml_file
        parsed_info = XMLParser(xml_file).critical_parse()
        if parsed_info.errors:
            raise forms.ValidationError(parsed_info.errors)
        return xml_file

    def clean(self):
        if self.shutdown:
            raise forms.ValidationError('The tool is shut down')
        self.staging_path = getattr(settings, 'STAGING_PATH', None)
        self.idnits = getattr(settings, 'IDNITS_PATH', None)
        if not self.staging_path:
            raise forms.ValidationError('STAGING_PATH not defined on settings.py')
        if not os.path.exists(self.staging_path):
            raise forms.ValidationError('STAGING_PATH defined on settings.py does not exist')
        if not self.idnits:
            raise forms.ValidationError('IDNITS_PATH not defined on settings.py')
        if not os.path.exists(self.idnits):
            raise forms.ValidationError('IDNITS_PATH defined on settings.py does not exist')
        if self.cleaned_data.get('txt', None):
            self.get_draft()
            self.check_previous_submission()
        return super(UploadForm, self).clean()

    def check_previous_submission(self):
        filename = self.draft.filename
        revision = self.draft.revision
        existing = IdSubmissionDetail.objects.filter(filename=filename, revision=revision,
                                                     status__pk__gte=0, status__pk__lt=100)
        if existing:
            raise forms.ValidationError('Duplicate Internet-Draft submission is currently in process.')

    def get_draft(self):
        if self.draft:
            return self.draft
        txt_file = self.cleaned_data['txt']
        txt_file.seek(0)
        self.draft = Draft(txt_file.read())
        txt_file.seek(0)
        return self.draft
    
    def save(self):
        for fd in [self.cleaned_data['txt'], self.cleaned_data['pdf'],
                   self.cleaned_data['xml'], self.cleaned_data['ps']]:
            if not fd:
                continue
            filename = os.path.join(self.staging_path, fd.name)
            destination = open(filename, 'wb+')
            for chunk in fd.chunks():
                destination.write(chunk)
                destination.close()
        self.check_idnits()
        return self.save_draft_info(self.draft)

    def check_idnits(self):
        filepath = os.path.join(self.staging_path, self.cleaned_data['txt'].name)
        p = subprocess.Popen([self.idnits, '--submitcheck', '--nitcount', filepath], stdout=subprocess.PIPE)
        self.idnits_message = p.stdout.read()

    def save_draft_info(self, draft):
        detail = IdSubmissionDetail.objects.create(
            id_document_name=draft.get_title(),
            filename=draft.filename,
            revision=draft.revision,
            txt_page_count=draft.get_pagecount(),
            creation_date=draft.get_creation_date(),
            idnits_message=self.idnits_message,
            status_id=1,  # Status 1 - upload
            )
        return detail
