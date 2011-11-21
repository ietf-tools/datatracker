import hashlib
import random
import os
import subprocess
import datetime

from django import forms
from django.forms.fields import email_re
from django.conf import settings
from django.contrib.sites.models import Site
from django.template.loader import render_to_string
from django.utils.html import mark_safe
from django.core.urlresolvers import reverse as urlreverse

from ietf.idtracker.models import InternetDraft, IETFWG
from ietf.proceedings.models import Meeting
from ietf.submit.models import IdSubmissionDetail, TempIdAuthors
from ietf.submit.utils import MANUAL_POST_REQUESTED, NONE_WG, UPLOADED, WAITING_AUTHENTICATION
from ietf.submit.parsers.pdf_parser import PDFParser
from ietf.submit.parsers.plain_parser import PlainParser
from ietf.submit.parsers.ps_parser import PSParser
from ietf.submit.parsers.xml_parser import XMLParser
from ietf.utils.mail import send_mail
from ietf.utils.draft import Draft


class UploadForm(forms.Form):

    txt = forms.FileField(label=u'.txt format', required=True)
    xml = forms.FileField(label=u'.xml format', required=False)
    pdf = forms.FileField(label=u'.pdf format', required=False)
    ps = forms.FileField(label=u'.ps format', required=False)

    fieldsets = [('Upload a draft', ('txt', 'xml', 'pdf', 'ps'))]

    class Media:
        css = {'all': ("/css/liaisons.css", )}

    def __init__(self, *args, **kwargs):
        self.request=kwargs.pop('request', None)
        self.remote_ip=self.request.META.get('REMOTE_ADDR', None)
        super(UploadForm, self).__init__(*args, **kwargs)
        self.in_first_cut_off = False
        self.idnits_message = None
        self.shutdown = False
        self.draft = None
        self.filesize = None
        self.group = None
        self.file_type = []
        self.read_dates()

    def read_dates(self):
        now = datetime.datetime.utcnow()
        first_cut_off = Meeting.get_first_cut_off()
        second_cut_off = Meeting.get_second_cut_off()
        ietf_monday = Meeting.get_ietf_monday()

        if now.date() >= first_cut_off and now.date() < second_cut_off:  # We are in the first_cut_off
            if now.date() == first_cut_off and now.hour < settings.CUTOFF_HOUR:
                self.cutoff_warning = 'The pre-meeting cutoff date for new documents (i.e., version -00 Internet-Drafts) is %s, at %02sh UTC. After that, you will not be able to submit a new document until %s, at %sh UTC' % (first_cut_off, settings.CUTOFF_HOUR, ietf_monday, settings.CUTOFF_HOUR, )
            else:  # No 00 version allowed
                self.cutoff_warning = 'The pre-meeting cutoff date for new documents (i.e., version -00 Internet-Drafts) was %s at %sh UTC. You will not be able to submit a new document until %s, at %sh UTC.<br>You can still submit a version -01 or higher Internet-Draft until %sh UTC, %s' % (first_cut_off, settings.CUTOFF_HOUR, ietf_monday, settings.CUTOFF_HOUR, settings.CUTOFF_HOUR, second_cut_off, )
                self.in_first_cut_off = True
        elif now.date() >= second_cut_off and now.date() < ietf_monday:
            if now.date() == second_cut_off and now.hour < settings.CUTOFF_HOUR:  # We are in the first_cut_off yet
                self.cutoff_warning = 'The pre-meeting cutoff date for new documents (i.e., version -00 Internet-Drafts) was %s at %02sh UTC. You will not be able to submit a new document until %s, at %02sh UTC.<br>The I-D submission tool will be shut down at %02sh UTC today, and reopened at %02sh UTC on %s' % (first_cut_off, settings.CUTOFF_HOUR, ietf_monday, settings.CUTOFF_HOUR, settings.CUTOFF_HOUR, settings.CUTOFF_HOUR, ietf_monday)
                self.in_first_cut_off = True
            else:  # Completely shut down of the tool
                self.cutoff_warning = 'The cut off time for the I-D submission was %02sh, %s.<br>The I-D submission tool will be reopened at %02sh, %s' % (settings.CUTOFF_HOUR, second_cut_off, settings.CUTOFF_HOUR, ietf_monday)
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
        self.filesize=txt_file.size
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
        self.check_paths()
        if self.cleaned_data.get('txt', None):
            self.get_draft()
            self.group=self.get_working_group()
            self.check_previous_submission()
            if self.draft.revision == '00' and self.in_first_cut_off:
                raise forms.ValidationError(mark_safe(self.cutoff_warning))
            self.check_tresholds()
        return super(UploadForm, self).clean()

    def check_tresholds(self):
        filename = self.draft.filename
        revision = self.draft.revision
        remote_ip = self.remote_ip
        today = datetime.date.today()

        # Same draft by name
        same_name = IdSubmissionDetail.objects.filter(filename=filename, revision=revision, submission_date=today)
        if same_name.count() > settings.MAX_SAME_DRAFT_NAME:
            raise forms.ValidationError('The same I-D cannot be submitted more than %s times a day' % settings.MAX_SAME_DRAFT_NAME)
        if sum([i.filesize for i in same_name]) > (settings.MAX_SAME_DRAFT_NAME_SIZE * 1048576):
            raise forms.ValidationError('The same I-D submission cannot exceed more than %s MByte a day' % settings.MAX_SAME_DRAFT_NAME_SIZE)

        # Total from same ip
        same_ip = IdSubmissionDetail.objects.filter(remote_ip=remote_ip, submission_date=today)
        if same_ip.count() > settings.MAX_SAME_SUBMITTER:
            raise forms.ValidationError('The same submitter cannot submit more than %s I-Ds a day' % settings.MAX_SAME_SUBMITTER)
        if sum([i.filesize for i in same_ip]) > (settings.MAX_SAME_SUBMITTER_SIZE * 1048576):
            raise forms.ValidationError('The same submitter cannot exceed more than %s MByte a day' % settings.MAX_SAME_SUBMITTER_SIZE)

        # Total in same group
        if self.group:
            same_group = IdSubmissionDetail.objects.filter(group_acronym=self.group, submission_date=today)
            if same_group.count() > settings.MAX_SAME_WG_DRAFT:
                raise forms.ValidationError('The same working group I-Ds cannot be submitted more than %s times a day' % settings.MAX_SAME_WG_DRAFT)
            if sum([i.filesize for i in same_group]) > (settings.MAX_SAME_WG_DRAFT_SIZE * 1048576):
                raise forms.ValidationError('Total size of same working group I-Ds cannot exceed %s MByte a day' % settings.MAX_SAME_WG_DRAFT_SIZE)


        # Total drafts for today
        total_today = IdSubmissionDetail.objects.filter(submission_date=today)
        if total_today.count() > settings.MAX_DAILY_SUBMISSION:
            raise forms.ValidationError('The total number of today\'s submission has reached the maximum number of submission per day')
        if sum([i.filesize for i in total_today]) > (settings.MAX_DAILY_SUBMISSION_SIZE * 1048576):
            raise forms.ValidationError('The total size of today\'s submission has reached the maximum size of submission per day')

    def check_paths(self):
        self.staging_path = getattr(settings, 'IDSUBMIT_STAGING_PATH', None)
        self.idnits = getattr(settings, 'IDSUBMIT_IDNITS_BINARY', None)
        if not self.staging_path:
            raise forms.ValidationError('IDSUBMIT_STAGING_PATH not defined in settings.py')
        if not os.path.exists(self.staging_path):
            raise forms.ValidationError('IDSUBMIT_STAGING_PATH defined in settings.py does not exist')
        if not self.idnits:
            raise forms.ValidationError('IDSUBMIT_IDNITS_BINARY not defined in settings.py')
        if not os.path.exists(self.idnits):
            raise forms.ValidationError('IDSUBMIT_IDNITS_BINARY defined in settings.py does not exist')

    def check_previous_submission(self):
        filename = self.draft.filename
        revision = self.draft.revision
        existing = IdSubmissionDetail.objects.filter(filename=filename, revision=revision,
                                                     status__pk__gte=0, status__pk__lt=100)
        if existing:
            raise forms.ValidationError(mark_safe('Duplicate Internet-Draft submission is currently in process. <a href="/submit/status/%s/">Check it here</a>' % existing[0].pk))

    def get_draft(self):
        if self.draft:
            return self.draft
        txt_file = self.cleaned_data['txt']
        txt_file.seek(0)
        self.draft = Draft(txt_file.read())
        txt_file.seek(0)
        return self.draft
    
    def save(self):
        for ext in ['txt', 'pdf', 'xml', 'ps']:
            fd = self.cleaned_data[ext]
            if not fd:
                continue
            self.file_type.append('.%s' % ext)
            filename = os.path.join(self.staging_path, '%s-%s.%s' % (self.draft.filename, self.draft.revision, ext))
            destination = open(filename, 'wb+')
            for chunk in fd.chunks():
                destination.write(chunk)
            destination.close()
        self.check_idnits()
        return self.save_draft_info(self.draft)

    def check_idnits(self):
        filepath = os.path.join(self.staging_path, '%s-%s.txt' % (self.draft.filename, self.draft.revision))
        p = subprocess.Popen([self.idnits, '--submitcheck', '--nitcount', filepath], stdout=subprocess.PIPE)
        self.idnits_message = p.stdout.read()

    def get_working_group(self):
        filename = self.draft.filename
        existing_draft = InternetDraft.objects.filter(filename=filename)
        if existing_draft:
            group = existing_draft[0].group and existing_draft[0].group.ietfwg or None
            if group and group.pk != NONE_WG:
                return group
            else:
                return None
        else:
            if filename.startswith('draft-ietf-'):
                # Extra check for WG that contains dashes
                for group in IETFWG.objects.filter(group_acronym__acronym__contains='-'):
                    if filename.startswith('draft-ietf-%s-' % group.group_acronym.acronym):
                        return group
                group_acronym = filename.split('-')[2]
                try:
                    return IETFWG.objects.get(group_acronym__acronym=group_acronym)
                except IETFWG.DoesNotExist:
                    raise forms.ValidationError('There is no active group with acronym \'%s\', please rename your draft' % group_acronym)
            else:
                return None

    def save_draft_info(self, draft):
        document_id = 0
        existing_draft = InternetDraft.objects.filter(filename=draft.filename)
        if existing_draft:
            if settings.USE_DB_REDESIGN_PROXY_CLASSES:
                document_id = -1
            else:
                document_id = existing_draft[0].id_document_tag
        detail = IdSubmissionDetail.objects.create(
            id_document_name=draft.get_title(),
            filename=draft.filename,
            revision=draft.revision,
            txt_page_count=draft.get_pagecount(),
            filesize=self.filesize,
            creation_date=draft.get_creation_date(),
            submission_date=datetime.date.today(),
            idnits_message=self.idnits_message,
            temp_id_document_tag=document_id,
            group_acronym=self.group,
            remote_ip=self.remote_ip,
            first_two_pages=''.join(draft.pages[:2]),
            status_id=UPLOADED,
            abstract=draft.get_abstract(),
            file_type=','.join(self.file_type),
            )
        order = 0
        for author in draft.get_author_info():
            full_name, first_name, middle_initial, last_name, name_suffix, email = author
            order += 1
            if settings.USE_DB_REDESIGN_PROXY_CLASSES:
                # save full name
                TempIdAuthors.objects.create(
                    id_document_tag=document_id,
                    first_name=full_name.strip(),
                    email_address=email,
                    author_order=order,
                    submission=detail)
            else:
                TempIdAuthors.objects.create(
                    id_document_tag=document_id,
                    first_name=first_name,
                    middle_initial=middle_initial,
                    last_name=last_name,
                    name_suffix=name_suffix,
                    email_address=email,
                    author_order=order,
                    submission=detail)
        return detail


class AutoPostForm(forms.Form):

    if settings.USE_DB_REDESIGN_PROXY_CLASSES:
        name = forms.CharField(required=True)
    else:
        first_name = forms.CharField(label=u'Given name', required=True)
        last_name = forms.CharField(label=u'Last name', required=True)
    email = forms.EmailField(label=u'Email address', required=True)

    def __init__(self, *args, **kwargs):
        self.draft = kwargs.pop('draft', None)
        self.validation = kwargs.pop('validation', None)
        super(AutoPostForm, self).__init__(*args, **kwargs)

    def get_author_buttons(self):
        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            buttons = []
            for i in self.validation.authors:
                buttons.append('<input type="button" data-name="%(name)s" data-email="%(email)s" value="%(name)s" />'
                               % dict(name=i.get_full_name(),
                                      email=i.email()[1] or ''))
            return "".join(buttons)


        # this should be moved to a Javascript file and attributes like data-first-name ...
        button_template = '<input type="button" onclick="jQuery(\'#id_first_name\').val(\'%(first_name)s\');jQuery(\'#id_last_name\').val(\'%(last_name)s\');jQuery(\'#id_email\').val(\'%(email)s\');" value="%(full_name)s" />'

        buttons = []
        for i in self.validation.authors:
            full_name = u'%s. %s' % (i.first_name[0], i.last_name)
            buttons.append(button_template % {'first_name': i.first_name,
                                              'last_name': i.last_name,
                                              'email': i.email()[1] or '',
                                              'full_name': full_name})
        return ''.join(buttons)

    def save(self, request):
        self.save_submitter_info()
        self.save_new_draft_info()
        self.send_confirmation_mail(request)

    def send_confirmation_mail(self, request):
        subject = 'Confirmation for Auto-Post of I-D %s' % self.draft.filename
        from_email = settings.IDSUBMIT_FROM_EMAIL
        to_email = self.cleaned_data['email']

        confirm_url = settings.IDTRACKER_BASE_URL + urlreverse('draft_confirm', kwargs=dict(submission_id=self.draft.submission_id, auth_key=self.draft.auth_key))
        status_url = settings.IDTRACKER_BASE_URL + urlreverse('draft_status_by_hash', kwargs=dict(submission_id=self.draft.submission_id, submission_hash=self.draft.get_hash()))
        
        send_mail(request, to_email, from_email, subject, 'submit/confirm_autopost.txt',
                  { 'draft': self.draft, 'confirm_url': confirm_url, 'status_url': status_url })

    def save_submitter_info(self):
        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            return TempIdAuthors.objects.create(
                id_document_tag=self.draft.temp_id_document_tag,
                first_name=self.cleaned_data['name'],
                email_address=self.cleaned_data['email'],
                author_order=0,
                submission=self.draft)

        return TempIdAuthors.objects.create(
            id_document_tag=self.draft.temp_id_document_tag,
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            email_address=self.cleaned_data['email'],
            author_order=0,
            submission=self.draft)

    def save_new_draft_info(self):
        salt = hashlib.sha1(str(random.random())).hexdigest()[:5]
        self.draft.auth_key = hashlib.sha1(salt+self.cleaned_data['email']).hexdigest()
        self.draft.status_id = WAITING_AUTHENTICATION
        self.draft.save()


class MetaDataForm(AutoPostForm):

    title = forms.CharField(label=u'Title', required=True)
    version = forms.CharField(label=u'Version', required=True)
    creation_date = forms.DateField(label=u'Creation date', required=True)
    pages = forms.IntegerField(label=u'Pages', required=True)
    abstract = forms.CharField(label=u'Abstract', widget=forms.Textarea, required=True)
    if settings.USE_DB_REDESIGN_PROXY_CLASSES:
        name = forms.CharField(required=True)
    else:
        first_name = forms.CharField(label=u'Given name', required=True)
        last_name = forms.CharField(label=u'Last name', required=True)
    email = forms.EmailField(label=u'Email address', required=True)
    comments = forms.CharField(label=u'Comments to the secretariat', widget=forms.Textarea, required=False)

    if settings.USE_DB_REDESIGN_PROXY_CLASSES:
        fields = ['title', 'version', 'creation_date', 'pages', 'abstract', 'name', 'email', 'comments']
    else:
        fields = ['title', 'version', 'creation_date', 'pages', 'abstract', 'first_name', 'last_name', 'email', 'comments']

    def __init__(self, *args, **kwargs):
        super(MetaDataForm, self).__init__(*args, **kwargs)
        self.set_initials()
        self.authors = self.get_initial_authors()

    def get_initial_authors(self):
        authors=[]
        if self.is_bound:
            for key, value in self.data.items():
                if settings.USE_DB_REDESIGN_PROXY_CLASSES:
                    if key.startswith('name_'):
                        author = {'errors': {}}
                        index = key.replace('name_', '')
                        name = value.strip()
                        if not name:
                            author['errors']['name'] = 'This field is required'
                        email = self.data.get('email_%s' % index, '').strip()
                        if email and not email_re.search(email):
                            author['errors']['email'] = 'Enter a valid e-mail address'
                        if name or email:
                            author.update({'get_full_name': name,
                                           'email': (name, email),
                                           'index': index,
                                           })
                            authors.append(author)

                else:
                    if key.startswith('first_name_'):
                        author = {'errors': {}}
                        index = key.replace('first_name_', '')
                        first_name = value.strip()
                        if not first_name:
                            author['errors']['first_name'] = 'This field is required'
                        last_name = self.data.get('last_name_%s' % index, '').strip()
                        if not last_name:
                            author['errors']['last_name'] = 'This field is required'
                        email = self.data.get('email_%s' % index, '').strip()
                        if email and not email_re.search(email):
                            author['errors']['email'] = 'Enter a valid e-mail address'
                        if first_name or last_name or email:
                            author.update({'first_name': first_name,
                                           'last_name': last_name,
                                           'email': ('%s %s' % (first_name, last_name), email),
                                           'index': index,
                                           })
                            authors.append(author)
            authors.sort(key=lambda x: x['index'])
        return authors

    def set_initials(self):
        self.fields['pages'].initial=self.draft.txt_page_count
        self.fields['creation_date'].initial=self.draft.creation_date
        self.fields['version'].initial=self.draft.revision
        self.fields['abstract'].initial=self.draft.abstract
        self.fields['title'].initial=self.draft.id_document_name

    def clean_creation_date(self):
        creation_date = self.cleaned_data.get('creation_date', None)
        if not creation_date:
            return None
        submit_date = self.draft.submission_date
        if (creation_date + datetime.timedelta(days=3) < submit_date or
            creation_date - datetime.timedelta(days=3) > submit_date):
            raise forms.ValidationError('Creation Date must be within 3 days of submission date')
        return creation_date

    def clean_version(self):
        version = self.cleaned_data.get('version', None)
        if not version:
            return None
        if len(version) > 2:
            raise forms.ValidationError('Version field is not in NN format')
        try:
            version_int = int(version)
        except ValueError:
            raise forms.ValidationError('Version field is not in NN format')
        if version_int > 99 or version_int < 0:
            raise forms.ValidationError('Version must be set between 00 and 99')
        existing_revisions = [int(i.revision_display()) for i in InternetDraft.objects.filter(filename=self.draft.filename)]
        expected = 0
        if existing_revisions:
            expected = max(existing_revisions) + 1
        if version_int != expected:
            raise forms.ValidationError('Invalid Version Number (Version %02d is expected)' % expected)
        return version

    def clean(self):
        if bool([i for i in self.authors if i['errors']]):
            raise forms.ValidationError('Please fix errors in author list')
        return super(MetaDataForm, self).clean()

    def get_authors(self):
        if not self.is_bound:
            return self.validation.get_authors()
        else:
            return self.authors

    def move_docs(self, draft, revision):
        old_revision = draft.revision
        for ext in draft.file_type.split(','):
            source = os.path.join(settings.IDSUBMIT_STAGING_PATH, '%s-%s%s' % (draft.filename, old_revision, ext))
            dest = os.path.join(settings.IDSUBMIT_STAGING_PATH, '%s-%s%s' % (draft.filename, revision, ext))
            os.rename(source, dest)

    def save_new_draft_info(self):
        draft = self.draft
        draft.id_document_name = self.cleaned_data['title']
        if draft.revision != self.cleaned_data['version']:
            self.move_docs(draft, self.cleaned_data['version'])
            draft.revision = self.cleaned_data['version']
        draft.creation_date = self.cleaned_data['creation_date']
        draft.txt_page_count = self.cleaned_data['pages']
        draft.abstract = self.cleaned_data['abstract']
        draft.comment_to_sec = self.cleaned_data['comments']
        draft.status_id = MANUAL_POST_REQUESTED
        draft.save()

        # sync authors
        draft.tempidauthors_set.all().delete()

        self.save_submitter_info() # submitter is author 0

        for i, author in enumerate(self.authors):
            if settings.USE_DB_REDESIGN_PROXY_CLASSES:
                # save full name
                TempIdAuthors.objects.create(
                    id_document_tag=draft.temp_id_document_tag,
                    first_name=author["get_full_name"],
                    email_address=author["email"][1],
                    author_order=i + 1,
                    submission=draft)

    def save(self, request):
        self.save_new_draft_info()
        self.send_mail_to_secretariat(request)

    def send_mail_to_secretariat(self, request):
        subject = 'Manual Post Requested for %s' % self.draft.filename
        from_email = settings.IDSUBMIT_FROM_EMAIL
        to_email = settings.IDSUBMIT_TO_EMAIL
        cc = [self.cleaned_data['email']]
        cc += [i['email'][1] for i in self.authors]
        if self.draft.group_acronym:
            cc += [i.person.email()[1] for i in self.draft.group_acronym.wgchair_set.all()]
        cc = list(set(cc))
        submitter = self.draft.tempidauthors_set.get(author_order=0)
        send_mail(request, to_email, from_email, subject, 'submit/manual_post_mail.txt', {
                'form': self,
                'draft': self.draft,
                'url': settings.IDTRACKER_BASE_URL + urlreverse('draft_status', kwargs=dict(submission_id=self.draft.submission_id)),
                'submitter': submitter
                },
                  cc=cc)
