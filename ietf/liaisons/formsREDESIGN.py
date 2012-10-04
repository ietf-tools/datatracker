import datetime, os
from email.utils import parseaddr

from django import forms
from django.conf import settings
from django.db.models import Q
from django.forms.util import ErrorList
from django.core.validators import email_re
from django.template.loader import render_to_string

from ietf.liaisons.accounts import (can_add_outgoing_liaison, can_add_incoming_liaison,
                                    get_person_for_user, is_secretariat, is_sdo_liaison_manager)
from ietf.liaisons.utils import IETFHM
from ietf.liaisons.widgets import (FromWidget, ReadOnlyWidget, ButtonWidget,
                                   ShowAttachmentsWidget, RelatedLiaisonWidget)
from ietf.liaisons.models import LiaisonStatement, LiaisonStatementPurposeName
from ietf.liaisons.proxy import LiaisonDetailProxy
from ietf.group.models import Group, Role
from ietf.person.models import Person, Email
from ietf.doc.models import Document


class LiaisonForm(forms.Form):
    person = forms.ModelChoiceField(Person.objects.all())
    from_field = forms.ChoiceField(widget=FromWidget, label=u'From')
    replyto = forms.CharField(label=u'Reply to')
    organization = forms.ChoiceField()
    to_poc = forms.CharField(widget=ReadOnlyWidget, label="POC", required=False)
    response_contact = forms.CharField(required=False, max_length=255)
    technical_contact = forms.CharField(required=False, max_length=255)
    cc1 = forms.CharField(widget=forms.Textarea, label="CC", required=False, help_text='Please insert one email address per line')
    purpose = forms.ChoiceField()
    purpose_text = forms.CharField(widget=forms.Textarea, label='Other purpose')
    deadline_date = forms.DateField(label='Deadline')
    submitted_date = forms.DateField(label='Submission date', initial=datetime.date.today())
    title = forms.CharField(label=u'Title')
    body = forms.CharField(widget=forms.Textarea, required=False)
    attachments = forms.CharField(label='Attachments', widget=ShowAttachmentsWidget, required=False)
    attach_title = forms.CharField(label='Title', required=False)
    attach_file = forms.FileField(label='File', required=False)
    attach_button = forms.CharField(label='',
                                    widget=ButtonWidget(label='Attach', show_on='id_attachments',
                                                        require=['id_attach_title', 'id_attach_file'],
                                                        required_label='title and file'),
                                    required=False)
    related_to = forms.ModelChoiceField(LiaisonStatement.objects.all(), label=u'Related Liaison', widget=RelatedLiaisonWidget, required=False)

    fieldsets = [('From', ('from_field', 'replyto')),
                 ('To', ('organization', 'to_poc')),
                 ('Other email addresses', ('response_contact', 'technical_contact', 'cc1')),
                 ('Purpose', ('purpose', 'purpose_text', 'deadline_date')),
                 ('References', ('related_to', )),
                 ('Liaison Statement', ('title', 'submitted_date', 'body', 'attachments')),
                 ('Add attachment', ('attach_title', 'attach_file', 'attach_button')),
                ]

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
            if is_secretariat(self.user) and 'from_fake_user' in kwargs['data'].keys():
                self.fake_person = Person.objects.get(pk=kwargs['data']['from_fake_user'])
                kwargs['data'].update({'person': self.fake_person.pk})
            else:
                kwargs['data'].update({'person': self.person.pk})

        self.instance = kwargs.pop("instance", None)
        
        super(LiaisonForm, self).__init__(*args, **kwargs)
        
        # now copy in values from instance, like a ModelForm
        if self.instance:
            for name, field in self.fields.iteritems():
                try:
                    x = getattr(self.instance, name)
                    if name == "purpose": # proxy has a name-clash on purpose so help it
                        x = x.order

                    try:
                        x = x.pk # foreign keys need the .pk, not the actual object
                    except AttributeError:
                        pass
                    self.initial[name] = x
                except AttributeError:
                    # we have some fields on the form that aren't in the model
                    pass
        self.fields["purpose"].choices = [("", "---------")] + [(str(l.order), l.name) for l in LiaisonStatementPurposeName.objects.all()]
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
        self.fields['replyto'].initial = self.person.email()[1]

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
        return ', '.join(u"%s <%s>" % i.email() for i in organization.get_poc())

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
        l = self.instance
        if not l:
            l = LiaisonDetailProxy()

        l.title = self.cleaned_data["title"]
        l.purpose = LiaisonStatementPurposeName.objects.get(order=self.cleaned_data["purpose"])
        l.body = self.cleaned_data["body"].strip()
        l.deadline = self.cleaned_data["deadline_date"]
        l.related_to = self.cleaned_data["related_to"]
        l.reply_to = self.cleaned_data["replyto"]
        l.response_contact = self.cleaned_data["response_contact"]
        l.technical_contact = self.cleaned_data["technical_contact"]
        
        now = datetime.datetime.now()
        
        l.modified = now
        l.submitted = datetime.datetime.combine(self.cleaned_data["submitted_date"], now.time())
        if not l.approved:
            l.approved = now

        self.save_extra_fields(l)
        
        l.save() # we have to save here to make sure we get an id for the attachments
        self.save_attachments(l)
        
        return l

    def save_extra_fields(self, liaison):
        from_entity = self.get_from_entity()
        liaison.from_name = from_entity.name
        liaison.from_group = from_entity.obj
        e = self.cleaned_data["person"].email_set.order_by('-active')
        if e:
            liaison.from_contact = e[0]

        organization = self.get_to_entity()
        liaison.to_name = organization.name
        liaison.to_group = organization.obj
        liaison.to_contact = self.get_poc(organization)

        liaison.cc = self.get_cc(from_entity, organization)

    def save_attachments(self, instance):
        written = instance.attachments.all().count()
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
            written += 1
            name = instance.name() + ("-attachment-%s" % written)
            attach = Document.objects.create(
                title = self.data.get(title_key),
                type_id = "liaison",
                name = name,
                external_url = name + extension, # strictly speaking not necessary, but just for the time being ...
                )
            instance.attachments.add(attach)
            attach_file = open(os.path.join(settings.LIAISON_ATTACH_PATH, attach.name + extension), 'w')
            attach_file.write(attached_file.read())
            attach_file.close()

    def clean_title(self):
        title = self.cleaned_data.get('title', None)
        if self.instance and self.instance.pk:
            exclude_filter = {'pk': self.instance.pk}
        else:
            exclude_filter = {}
        exists = bool(LiaisonStatement.objects.exclude(**exclude_filter).filter(title__iexact=title).count())
        if exists:
            raise forms.ValidationError('A liaison statement with the same title has previously been submitted.')
        return title


class IncomingLiaisonForm(LiaisonForm):

    def set_from_field(self):
        if is_secretariat(self.user):
            sdos = Group.objects.filter(type="sdo", state="active")
        else:
            sdos = Group.objects.filter(type="sdo", state="active", role__person=self.person, role__name__in=("liaiman", "auth")).distinct()
        self.fields['from_field'].choices = [('sdo_%s' % i.pk, i.name) for i in sdos.order_by("name")]
        self.fields['from_field'].widget.submitter = unicode(self.person)

    def set_replyto_field(self):
        e = Email.objects.filter(person=self.person, role__group__state="active", role__name__in=["liaiman", "auth"])
        if e:
            addr = e[0].address
        else:
            addr = self.person.email_address()
        self.fields['replyto'].initial = addr

    def set_organization_field(self):
        self.fields['organization'].choices = self.hm.get_all_incoming_entities()

    def get_post_only(self):
        from_entity = self.get_from_entity()
        if is_secretariat(self.user) or Role.objects.filter(person=self.person, group=from_entity.obj, name="auth"):
            return False
        return True

    def clean(self):
        if 'send' in self.data.keys() and self.get_post_only():
            self._errors['from_field'] = ErrorList([u'As an IETF Liaison Manager you can not send an incoming liaison statements, you only can post them'])
        return super(IncomingLiaisonForm, self).clean()


def liaison_manager_sdos(person):
    return Group.objects.filter(type="sdo", state="active", role__person=person, role__name="liaiman").distinct()

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
                self.fields['from_field'].widget.reduced_to_set = ['sdo_%s' % i.pk for i in liaison_manager_sdos(self.person)]
        else:
            self.fields['from_field'].choices = self.hm.get_entities_for_person(self.person)
        self.fields['from_field'].widget.submitter = unicode(self.person)
        self.fieldsets[0] = ('From', ('from_field', 'replyto', 'approved'))

    def set_replyto_field(self):
        e = Email.objects.filter(person=self.person, role__group__state="active", role__name__in=["ad", "chair"])
        if e:
            addr = e[0].address
        else:
            addr = self.person.email_address()
        self.fields['replyto'].initial = addr

    def set_organization_field(self):
        # If the user is a liaison manager and is nothing more, reduce the To field to his SDOs
        if not self.hm.get_entities_for_person(self.person) and is_sdo_liaison_manager(self.person):
            self.fields['organization'].choices = [('sdo_%s' % i.pk, i.name) for i in liaison_manager_sdos(self.person)]
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
            liaison.approved = datetime.datetime.now()
        else:
            liaison.approved = None

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
        sdo_codes = ['sdo_%s' % i.pk for i in liaison_manager_sdos(person)]
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
        liaison.from_name = self.cleaned_data.get('from_field')
        liaison.to_name = self.cleaned_data.get('organization')
        liaison.to_contact = self.cleaned_data['to_poc']
        liaison.cc = self.cleaned_data['cc1']

