import datetime

from django import forms
from django.conf import settings
from django.forms.util import ErrorList
from django.template.loader import render_to_string

from ietf.liaisons.accounts import (can_add_outgoing_liaison, can_add_incoming_liaison,
                                    get_person_for_user)
from ietf.liaisons.models import LiaisonDetail, Uploads
from ietf.liaisons.utils import IETFHierarchyManager
from ietf.liaisons.widgets import (FromWidget, ReadOnlyWidget, ButtonWidget,
                                   ShowAttachmentsWidget)


class LiaisonForm(forms.ModelForm):

    from_field = forms.ChoiceField(widget=FromWidget, label=u'From')
    replyto = forms.CharField(label=u'Reply to')
    organization = forms.ChoiceField()
    to_poc = forms.CharField(widget=ReadOnlyWidget, label="POC", required=False)
    cc1 = forms.CharField(widget=ReadOnlyWidget, label="CC", required=False)
    purpose_text = forms.CharField(widget=forms.Textarea, label='Other purpose')
    deadline_date = forms.DateField(label='Deadline')
    title = forms.CharField(label=u'Title')
    attachments = forms.CharField(label='Attachments', widget=ShowAttachmentsWidget, required=False)
    attach_title = forms.CharField(label='Title', required=False)
    attach_file = forms.FileField(label='File', required=False)
    attach_button = forms.CharField(label='',
                                    widget=ButtonWidget(label='Attach', show_on='id_attachments',
                                                        require=['id_attach_title', 'id_attach_file'],
                                                        required_label='title and file'),
                                    required=False)

    fieldsets = (('From', ('from_field', 'replyto')),
                 ('To', ('organization', 'to_poc')),
                 ('Other email addresses', ('response_contact', 'technical_contact', 'cc1')),
                 ('Purpose', ('purpose', 'purpose_text', 'deadline_date')),
                 ('Liaison Statement', ('title', 'body', 'attachments')),
                 ('Add attachment', ('attach_title', 'attach_file', 'attach_button')),
                )

    class Meta:
        model = LiaisonDetail

    class Media:
        js = ("/js/jquery-1.4.2.min.js",
              "/js/jquery-ui-1.8.2.custom.min.js",
              "/js/liaisons.js", )

        css = {'all': ("/css/liaisons.css",
                       "/css/jquery-ui-themes/jquery-ui-1.8.2.custom.css")}

    def __init__(self, user, *args, **kwargs):
        self.person = get_person_for_user(user)
        if kwargs.get('data', None):
            kwargs['data'].update({'person': self.person.pk})
        super(LiaisonForm, self).__init__(*args, **kwargs)
        self.hm = IETFHierarchyManager()
        self.set_from_field()
        self.set_replyto_field()
        self.set_organization_field()

    def __unicode__(self):
        return self.as_div()

    def set_purpose_required_fields(self):
        purpose = self.data.get('purpose', None)
        if purpose == '5':
            self.fields['purpose_text'].required=True
        else:
            self.fields['purpose_text'].required=False
        if purpose in ['1', '2']:
            self.fields['deadline_date'].required=True
        else:
            self.fields['deadline_date'].required=False

    def reset_purpose_required_fields(self):
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
        self.set_purpose_required_fields()
        super(LiaisonForm, self).full_clean()
        self.reset_purpose_required_fields()

    def has_attachments(self):
        for key in self.files.keys():
            if key.startswith('attach_file_') and key.replace('file', 'title') in self.data.keys():
                return True
        return False

    def clean(self):
        if not self.cleaned_data.get('body', None) and not self.has_attachments():
            self._errors['body'] = ErrorList([u'You must provide a body or attachment files'])
            self._errors['attachments'] = ErrorList([u'You must provide a body or attachment files'])
        return self.cleaned_data

    def get_organization(self):
        organization_key = self.cleaned_data.get('organization')
        return self.hm.get_entity_by_key(organization_key)

    def save(self, *args, **kwargs):
        now = datetime.datetime.now()
        liaison = super(LiaisonForm, self).save(*args, **kwargs)
        liaison.submitted_date = now
        liaison.last_modified_date = now
        organization =  self.get_organization()
        liaison.to_body = organization.name
        liaison.to_poc = ', '.join([i.email()[1] for i in organization.get_poc()])
        liaison.submitter_name, liaison.submitter_email = self.person.email()
        liaison.cc1 = ', '.join(['%s <%s>' % i.email() for i in organization.get_cc()])
        liaison.save()
        self.save_attachments(liaison)

    def save_attachments(self, instance):
        for key in self.files.keys():
            title_key = key.replace('file', 'title')
            if not key.startswith('attach_file_') or not title_key in self.data.keys():
                continue
            attached_file = self.files.get(key)
            extension=attached_file.name.rsplit('.', 1)
            basename = extension[0]
            if len(extension) > 1:
                extension = '.' + extension[1]
            else:
                extension = ''
            attach = Uploads.objects.create(
                file_title = self.data.get(title_key),
                person = self.person,
                detail = instance,
                file_extension = extension
                )


class IncomingLiaisonForm(LiaisonForm):

    def set_from_field(self):
        sdo_managed = [i.sdo for i in self.person.liaisonmanagers_set.all()]
        sdo_authorized = [i.sdo for i in self.person.sdoauthorizedindividual_set.all()]
        sdos = set(sdo_managed).union(sdo_authorized)
        self.fields['from_field'].choices = [(i.pk, i.sdo_name) for i in sdos]
        self.fields['from_field'].widget.submitter = unicode(self.person)

    def set_organization_field(self):
        self.fields['organization'].choices = self.hm.get_all_decorated_entities()


class OutgoingLiaisonForm(LiaisonForm):

    def set_from_field(self):
        pass

    def set_organization_field(self):
        pass


def liaison_form_factory(request, **kwargs):
    user = request.user
    if can_add_incoming_liaison(user):
        return IncomingLiaisonForm(user, **kwargs)
    elif can_add_outgoing_liaison(user):
        return OutgoingLiaisonForm(user, **kwargs)
    return None
