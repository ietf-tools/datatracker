import datetime
from email.utils import parseaddr

from django import forms
from django.conf import settings
from django.db.models import Q
from django.forms.util import ErrorList
from django.forms.fields import email_re
from django.template.loader import render_to_string

from ietf.idtracker.models import PersonOrOrgInfo
from ietf.liaisons.accounts import (can_add_outgoing_liaison, can_add_incoming_liaison,
                                    get_person_for_user, is_secretariat, is_sdo_liaison_manager)
from ietf.liaisons.models import LiaisonDetail, Uploads, OutgoingLiaisonApproval, SDOs
from ietf.liaisons.utils import IETFHM
from ietf.liaisons.widgets import (FromWidget, ReadOnlyWidget, ButtonWidget,
                                   ShowAttachmentsWidget, RelatedLiaisonWidget)


class LiaisonForm(forms.ModelForm):

    from_field = forms.ChoiceField(widget=FromWidget, label=u'From')
    replyto = forms.CharField(label=u'Reply to')
    organization = forms.ChoiceField()
    to_poc = forms.CharField(widget=ReadOnlyWidget, label="POC", required=False)
    cc1 = forms.CharField(widget=forms.Textarea, label="CC", required=False, help_text='Please insert one email address per line')
    purpose_text = forms.CharField(widget=forms.Textarea, label='Other purpose')
    deadline_date = forms.DateField(label='Deadline')
    submitted_date = forms.DateField(label='Submission date', initial=datetime.date.today())
    title = forms.CharField(label=u'Title')
    attachments = forms.CharField(label='Attachments', widget=ShowAttachmentsWidget, required=False)
    attach_title = forms.CharField(label='Title', required=False)
    attach_file = forms.FileField(label='File', required=False)
    attach_button = forms.CharField(label='',
                                    widget=ButtonWidget(label='Attach', show_on='id_attachments',
                                                        require=['id_attach_title', 'id_attach_file'],
                                                        required_label='title and file'),
                                    required=False)
    related_to = forms.ModelChoiceField(LiaisonDetail.objects.all(), label=u'Related Liaison', widget=RelatedLiaisonWidget, required=False)

    fieldsets = [('From', ('from_field', 'replyto')),
                 ('To', ('organization', 'to_poc')),
                 ('Other email addresses', ('response_contact', 'technical_contact', 'cc1')),
                 ('Purpose', ('purpose', 'purpose_text', 'deadline_date')),
                 ('References', ('related_to', )),
                 ('Liaison Statement', ('title', 'submitted_date', 'body', 'attachments')),
                 ('Add attachment', ('attach_title', 'attach_file', 'attach_button')),
                ]

    class Meta:
        model = LiaisonDetail

    class Media:
        js = ("/js/jquery-1.5.1.min.js",
              "/js/jquery-ui-1.8.11.custom.min.js",
              "/js/liaisons.js", )

        css = {'all': ("/css/liaisons.css",
                       "/css/jquery-ui-themes/jquery-ui-1.8.11.custom.css")}

    def __init__(self, user, *args, **kwargs):
        self.user = user
        self.fake_person = None
        self.person = get_person_for_user(user)
        if kwargs.get('data', None):
            kwargs['data'].update({'person': self.person.pk})
            if is_secretariat(self.user) and 'from_fake_user' in kwargs['data'].keys():
                self.fake_person = PersonOrOrgInfo.objects.get(pk=kwargs['data']['from_fake_user'])
                kwargs['data'].update({'person': self.fake_person.pk})
        super(LiaisonForm, self).__init__(*args, **kwargs)
        self.hm = IETFHM
        self.set_from_field()
        self.set_replyto_field()
        self.set_organization_field()

    def __unicode__(self):
        return self.as_div()

    def get_post_only(self):
        return False

    def set_required_fields(self):
        purpose = self.data.get('purpose', None)
        if purpose == '5':
            self.fields['purpose_text'].required=True
        else:
            self.fields['purpose_text'].required=False
        if purpose in ['1', '2']:
            self.fields['deadline_date'].required=True
        else:
            self.fields['deadline_date'].required=False

    def reset_required_fields(self):
        self.fields['purpose_text'].required=True
        self.fields['deadline_date'].required=True

    def set_from_field(self):
        assert NotImplemented

    def set_replyto_field(self):
        email = self.person.email()
        self.fields['replyto'].initial = email and email[1]

    def set_organization_field(self):
        assert NotImplemented

    def as_div(self):
        return render_to_string('liaisons/liaisonform.html', {'form': self})

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

    def full_clean(self):
        self.set_required_fields()
        super(LiaisonForm, self).full_clean()
        self.reset_required_fields()

    def has_attachments(self):
        for key in self.files.keys():
            if key.startswith('attach_file_') and key.replace('file', 'title') in self.data.keys():
                return True
        return False

    def check_email(self, value):
        if not value:
            return
        emails = value.split(',')
        for email in emails:
            name, addr = parseaddr(email)
            if not email_re.search(addr):
                raise forms.ValidationError('Invalid email address: %s' % addr)

    def clean_response_contact(self):
        value = self.cleaned_data.get('response_contact', None)
        self.check_email(value)
        return value

    def clean_technical_contact(self):
        value = self.cleaned_data.get('technical_contact', None)
        self.check_email(value)
        return value

    def clean_reply_to(self):
        value = self.cleaned_data.get('reply_to', None)
        self.check_email(value)
        return value

    def clean(self):
        if not self.cleaned_data.get('body', None) and not self.has_attachments():
            self._errors['body'] = ErrorList([u'You must provide a body or attachment files'])
            self._errors['attachments'] = ErrorList([u'You must provide a body or attachment files'])
        return self.cleaned_data

    def get_from_entity(self):
        organization_key = self.cleaned_data.get('from_field')
        return self.hm.get_entity_by_key(organization_key)

    def get_to_entity(self):
        organization_key = self.cleaned_data.get('organization')
        return self.hm.get_entity_by_key(organization_key)

    def get_poc(self, organization):
        return ', '.join([i.email()[1] for i in organization.get_poc()])

    def clean_cc1(self):
        value = self.cleaned_data.get('cc1', '')
        result = []
        errors = []
        for address in value.split('\n'):
            address = address.strip();
            if not address:
                continue
            try:
                self.check_email(address)
            except forms.ValidationError:
                errors.append(address)
            result.append(address)
        if errors:
            raise forms.ValidationError('Invalid email addresses: %s' % ', '.join(errors))
        return ','.join(result)

    def get_cc(self, from_entity, to_entity):
        #Old automatic Cc code, now we retrive it from cleaned_data
        #persons = to_entity.get_cc(self.person)
        #persons += from_entity.get_from_cc(self.person)
        #return ', '.join(['%s <%s>' % i.email() for i in persons])
        cc = self.cleaned_data.get('cc1', '')
        return cc

    def save(self, *args, **kwargs):
        liaison = super(LiaisonForm, self).save(*args, **kwargs)
        self.save_extra_fields(liaison)
        self.save_attachments(liaison)
        return liaison

    def save_extra_fields(self, liaison):
        now = datetime.datetime.now()
        liaison.last_modified_date = now
        from_entity = self.get_from_entity()
        liaison.from_raw_body = from_entity.name
        liaison.from_raw_code = self.cleaned_data.get('from_field')
        organization = self.get_to_entity()
        liaison.to_raw_code = self.cleaned_data.get('organization')
        liaison.to_body = organization.name
        liaison.to_poc = self.get_poc(organization)
        liaison.submitter_name, liaison.submitter_email = self.person.email()
        liaison.cc1 = self.get_cc(from_entity, organization)
        liaison.save()

    def save_attachments(self, instance):
        for key in self.files.keys():
            title_key = key.replace('file', 'title')
            if not key.startswith('attach_file_') or not title_key in self.data.keys():
                continue
            attached_file = self.files.get(key)
            extension=attached_file.name.rsplit('.', 1)
            if len(extension) > 1:
                extension = '.' + extension[1]
            else:
                extension = ''
            attach = Uploads.objects.create(
                file_title = self.data.get(title_key),
                person = self.person,
                detail = instance,
                file_extension = extension,
                )
            attach_file = open('%sfile%s%s' % (settings.LIAISON_ATTACH_PATH, attach.pk, attach.file_extension), 'w')
            attach_file.write(attached_file.read())
            attach_file.close()

    def clean_title(self):
        title = self.cleaned_data.get('title', None)
        if self.instance and self.instance.pk:
            exclude_filter = {'pk': self.instance.pk}
        else:
            exclude_filter = {}
        exists = bool(LiaisonDetail.objects.exclude(**exclude_filter).filter(title__iexact=title).count())
        if exists:
            raise forms.ValidationError('A liaison statement with the same title has previously been submitted.')
        return title


class IncomingLiaisonForm(LiaisonForm):

    def set_from_field(self):
        if is_secretariat(self.user):
            sdos = SDOs.objects.all()
        else:
            sdo_managed = [i.sdo for i in self.person.liaisonmanagers_set.all()]
            sdo_authorized = [i.sdo for i in self.person.sdoauthorizedindividual_set.all()]
            sdos = set(sdo_managed).union(sdo_authorized)
        self.fields['from_field'].choices = [('sdo_%s' % i.pk, i.sdo_name) for i in sdos]
        self.fields['from_field'].widget.submitter = unicode(self.person)

    def set_organization_field(self):
        self.fields['organization'].choices = self.hm.get_all_incoming_entities()

    def get_post_only(self):
        from_entity = self.get_from_entity()
        if is_secretariat(self.user) or self.person.sdoauthorizedindividual_set.filter(sdo=from_entity.obj):
            return False
        return True

    def clean(self):
        if 'send' in self.data.keys() and self.get_post_only():
            self._errors['from_field'] = ErrorList([u'As an IETF Liaison Manager you can not send an incoming liaison statements, you only can post them'])
        return super(IncomingLiaisonForm, self).clean()


class OutgoingLiaisonForm(LiaisonForm):

    to_poc = forms.CharField(label="POC", required=True)
    approved = forms.BooleanField(label="Obtained prior approval", required=False)
    other_organization = forms.CharField(label="Other SDO", required=True)

    def get_to_entity(self):
        organization_key = self.cleaned_data.get('organization')
        organization = self.hm.get_entity_by_key(organization_key)
        if organization_key == 'othersdo' and self.cleaned_data.get('other_organization', None):
            organization.name=self.cleaned_data['other_organization']
        return organization

    def set_from_field(self):
        if is_secretariat(self.user): 
            self.fields['from_field'].choices = self.hm.get_all_incoming_entities()
        elif is_sdo_liaison_manager(self.person):
            self.fields['from_field'].choices = self.hm.get_all_incoming_entities()
            all_entities = []
            for i in self.hm.get_entities_for_person(self.person):
                all_entities += i[1]
            if all_entities:
                self.fields['from_field'].widget.full_power_on = [i[0] for i in all_entities]
                self.fields['from_field'].widget.reduced_to_set = ['sdo_%s' % i.sdo.pk for i in self.person.liaisonmanagers_set.all().distinct()]
        else:
            self.fields['from_field'].choices = self.hm.get_entities_for_person(self.person)
        self.fields['from_field'].widget.submitter = unicode(self.person)
        self.fieldsets[0] = ('From', ('from_field', 'replyto', 'approved'))

    def set_organization_field(self):
        # If the user is a liaison manager and is nothing more, reduce the To field to his SDOs
        if not self.hm.get_entities_for_person(self.person) and is_sdo_liaison_manager(self.person):
            sdos = [i.sdo for i in self.person.liaisonmanagers_set.all().distinct()]
            self.fields['organization'].choices = [('sdo_%s' % i.pk, i.sdo_name) for i in sdos]
        else:
            self.fields['organization'].choices = self.hm.get_all_outgoing_entities()
        self.fieldsets[1] = ('To', ('organization', 'other_organization', 'to_poc'))

    def set_required_fields(self):
        super(OutgoingLiaisonForm, self).set_required_fields()
        organization = self.data.get('organization', None)
        if organization == 'othersdo':
            self.fields['other_organization'].required=True
        else:
            self.fields['other_organization'].required=False

    def reset_required_fields(self):
        super(OutgoingLiaisonForm, self).reset_required_fields()
        self.fields['other_organization'].required=True

    def get_poc(self, organization):
        return self.cleaned_data['to_poc']

    def save_extra_fields(self, liaison):
        super(OutgoingLiaisonForm, self).save_extra_fields(liaison)
        from_entity = self.get_from_entity()
        needs_approval = from_entity.needs_approval(self.person)
        if not needs_approval or self.cleaned_data.get('approved', False):
            approved = True
            approval_date = datetime.datetime.now()
        else:
            approved = False
            approval_date = None
        approval = OutgoingLiaisonApproval.objects.create(
            approved = approved,
            approval_date = approval_date)
        liaison.approval = approval
        liaison.save()

    def clean_to_poc(self):
        value = self.cleaned_data.get('to_poc', None)
        self.check_email(value)
        return value

    def clean_organization(self):
        to_code = self.cleaned_data.get('organization', None)
        from_code = self.cleaned_data.get('from_field', None)
        if not to_code or not from_code:
            return to_code
        all_entities = []
        person = self.fake_person or self.person
        for i in self.hm.get_entities_for_person(person):
            all_entities += i[1]
        # If the from entity is one in wich the user has full privileges the to entity could be anyone
        if from_code in [i[0] for i in all_entities]:
            return to_code
        sdo_codes = ['sdo_%s' % i.sdo.pk for i in person.liaisonmanagers_set.all().distinct()]
        if to_code in sdo_codes:
            return to_code
        entity = self.get_to_entity()
        entity_name = entity and entity.name or to_code
        if self.fake_person:
            raise forms.ValidationError('%s is not allowed to send a liaison to: %s' % (self.fake_person, entity_name))
        else:
            raise forms.ValidationError('You are not allowed to send a liaison to: %s' % entity_name)


class EditLiaisonForm(LiaisonForm):

    from_field = forms.CharField(widget=forms.TextInput, label=u'From')
    replyto = forms.CharField(label=u'Reply to', widget=forms.TextInput)
    organization = forms.CharField(widget=forms.TextInput)
    to_poc = forms.CharField(widget=forms.TextInput, label="POC", required=False)
    cc1 = forms.CharField(widget=forms.TextInput, label="CC", required=False)

    class Meta:
        model = LiaisonDetail
        fields = ('from_raw_body', 'to_body', 'to_poc', 'cc1', 'last_modified_date', 'title',
                  'response_contact', 'technical_contact', 'purpose_text', 'body',
                  'deadline_date', 'purpose', 'replyto', 'related_to')

    def __init__(self, *args, **kwargs):
        super(EditLiaisonForm, self).__init__(*args, **kwargs)
        self.edit = True
        self.initial.update({'attachments': self.instance.uploads_set.all()})
        self.fields['submitted_date'].initial = self.instance.submitted_date

    def set_from_field(self):
        self.fields['from_field'].initial = self.instance.from_body

    def set_replyto_field(self):
        self.fields['replyto'].initial = self.instance.replyto

    def set_organization_field(self):
        self.fields['organization'].initial = self.instance.to_body

    def save_extra_fields(self, liaison):
        now = datetime.datetime.now()
        liaison.last_modified_date = now
        liaison.from_raw_body = self.cleaned_data.get('from_field')
        liaison.to_body = self.cleaned_data.get('organization')
        liaison.to_poc = self.cleaned_data['to_poc']
        liaison.cc1 = self.cleaned_data['cc1']
        liaison.save()


def liaison_form_factory(request, **kwargs):
    user = request.user
    force_incoming = 'incoming' in request.GET.keys()
    liaison = kwargs.pop('liaison', None)
    if liaison:
        return EditLiaisonForm(user, instance=liaison, **kwargs)
    if not force_incoming and can_add_outgoing_liaison(user):
        return OutgoingLiaisonForm(user, **kwargs)
    elif can_add_incoming_liaison(user):
        return IncomingLiaisonForm(user, **kwargs)
    return None
