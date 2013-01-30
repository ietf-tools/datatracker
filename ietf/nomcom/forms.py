from django.conf import settings
from django import forms
from django.contrib.formtools.preview import FormPreview, AUTO_ID
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.core.urlresolvers import reverse
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.shortcuts import render_to_response
from django.template.context import RequestContext

from ietf.dbtemplate.forms import DBTemplateForm
from ietf.utils import unaccent
from ietf.utils.mail import send_mail
from ietf.ietfauth.decorators import role_required
from ietf.utils import fields as custom_fields
from ietf.group.models import Group, Role
from ietf.name.models import RoleName, FeedbackType
from ietf.person.models import Email, Person
from ietf.nomcom.models import NomCom, Nomination, Nominee, NomineePosition, \
                               Position, Feedback
from ietf.nomcom.utils import QUESTIONNAIRE_TEMPLATE, NOMINATION_EMAIL_TEMPLATE, \
                              INEXISTENT_PERSON_TEMPLATE, NOMINEE_EMAIL_TEMPLATE, \
                              get_user_email
from ietf.nomcom.decorators import member_required

ROLODEX_URL = getattr(settings, 'ROLODEX_URL', None)


def get_group_or_404(year):
    return get_object_or_404(Group,
                             acronym__icontains=year,
                             state__slug='active',
                             nomcom__isnull=False)


def get_list(string):
        return map(unicode.strip, string.replace('\r\n', '').split(','))


class BaseNomcomForm(object):
    def __unicode__(self):
        return self.as_div()

    def as_div(self):
        return render_to_string('nomcom/nomcomform.html', {'form': self})

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


class EditMembersForm(BaseNomcomForm, forms.Form):

    members = custom_fields.MultiEmailField(label="Members email", required=False)

    fieldsets = [('Members', ('members',))]


class EditMembersFormPreview(FormPreview):
    form_template = 'nomcom/edit_members.html'
    preview_template = 'nomcom/edit_members_preview.html'

    @method_decorator(member_required(role='chair'))
    def __call__(self, request, *args, **kwargs):
        year = kwargs['year']
        group = get_group_or_404(year)
        self.state['group'] = group
        self.state['rolodex_url'] = ROLODEX_URL
        self.group = group
        self.year = year

        return super(EditMembersFormPreview, self).__call__(request, *args, **kwargs)

    def preview_get(self, request):
        "Displays the form"
        f = self.form(auto_id=AUTO_ID)
        return render_to_response(self.form_template,
                                  {'form': f,
                                  'stage_field': self.unused_name('stage'),
                                  'state': self.state,
                                  'year': self.year,
                                  'selected': 'edit_members'},
                                  context_instance=RequestContext(request))

    def parse_params(self, *args, **kwargs):
        members = self.group.role_set.filter(name__slug='member')

        if members:
            self.form.base_fields['members'].initial = ',\r\n'.join([role.email.address for role in members])

    def process_preview(self, request, form, context):
        members_email = get_list(form.cleaned_data['members'])

        members_info = []
        emails_not_found = []

        for email in members_email:
            try:
                email_obj = Email.objects.get(address=email)
                person = email_obj.person
            except Email.DoesNotExist:
                person = None
            if person:
                members_info.append({'email': email,
                                     'email_obj': email_obj,
                                     'person': person})
            else:
                emails_not_found.append(email)
        self.state.update({'members_info': members_info,
                           'emails_not_found': emails_not_found})

    def done(self, request, cleaned_data):
        members_info = self.state['members_info']
        members_email = [member['email'] for member in self.state['members_info']]
        members_excluded = self.group.role_set.filter(name__slug='member').exclude(email__address__in=members_email)
        members_excluded.delete()
        for member in members_info:
            Role.objects.get_or_create(name=RoleName.objects.get(slug="member"),
                                       group=self.group,
                                       person=member['person'],
                                       email=member['email_obj'])

        return HttpResponseRedirect(reverse('nomcom_edit_members', kwargs={'year': self.year}))


class EditChairForm(BaseNomcomForm, forms.Form):

    chair = forms.EmailField(label="Chair email", required=False,
                             widget=forms.TextInput(attrs={'size': '40'}))

    fieldsets = [('Chair info', ('chair',))]


class EditChairFormPreview(FormPreview):
    form_template = 'nomcom/edit_chair.html'
    preview_template = 'nomcom/edit_chair_preview.html'

    @method_decorator(role_required("Secretariat"))
    def __call__(self, request, *args, **kwargs):
        year = kwargs['year']
        group = get_group_or_404(year)
        self.state['group'] = group
        self.state['rolodex_url'] = ROLODEX_URL
        self.group = group
        self.year = year

        return super(EditChairFormPreview, self).__call__(request, *args, **kwargs)

    def parse_params(self, *args, **kwargs):
        chair = self.group.get_chair()
        if chair:
            self.form.base_fields['chair'].initial = chair.email.address

    def process_preview(self, request, form, context):
        chair_email = form.cleaned_data['chair']
        try:
            chair_email_obj = Email.objects.get(address=chair_email)
            chair_person = chair_email_obj.person
        except Email.DoesNotExist:
            chair_person = None
            chair_email_obj = None
        chair_info = {'email': chair_email,
                      'email_obj': chair_email_obj,
                      'person': chair_person}

        self.state.update({'chair_info': chair_info})

    def done(self, request, cleaned_data):
        chair_info = self.state['chair_info']
        chair_exclude = self.group.role_set.filter(name__slug='chair').exclude(email__address=chair_info['email'])
        chair_exclude.delete()
        if chair_info['email_obj'] and chair_info['person']:
            Role.objects.get_or_create(name=RoleName.objects.get(slug="chair"),
                                      group=self.group,
                                      person=chair_info['person'],
                                      email=chair_info['email_obj'])

        return HttpResponseRedirect(reverse('nomcom_edit_chair', kwargs={'year': self.year}))


class EditPublicKeyForm(BaseNomcomForm, forms.ModelForm):

    fieldsets = [('Public Key', ('public_key',))]

    class Meta:
        model = NomCom
        fields = ('public_key',)

    def __init__(self, *args, **kwargs):
        super(EditPublicKeyForm, self).__init__(*args, **kwargs)
        self.fields['public_key'].required = True


class MergeForm(BaseNomcomForm, forms.Form):

    secondary_emails = custom_fields.MultiEmailField(label="Secondary email address (remove this):")
    primary_email = forms.EmailField(label="Primary email address",
                                     widget=forms.TextInput(attrs={'size': '40'}))

    fieldsets = [('Emails', ('primary_email', 'secondary_emails'))]

    def __init__(self, *args, **kwargs):
        self.nomcom = kwargs.pop('nomcom', None)
        super(MergeForm, self).__init__(*args, **kwargs)

    def clean_primary_email(self):
        email = self.cleaned_data['primary_email']
        nominees = Nominee.objects.filter(email__address=email,
                                         nominee_position__nomcom=self.nomcom)
        if not nominees:
            msg = "Does not exist a nomiee with this email"
            self._errors["primary_email"] = self.error_class([msg])

        return email

    def clean_secondary_emails(self):
        data = self.cleaned_data['secondary_emails']
        emails = get_list(data)
        for email in emails:
            nominees = Nominee.objects.filter(email__address=email,
                                         nominee_position__nomcom=self.nomcom)
            if not nominees:
                msg = "Does not exist a nomiee with email %s" % email
                self._errors["primary_email"] = self.error_class([msg])
            break

        return data

    def clean(self):
        primary_email = self.cleaned_data.get("primary_email")
        secondary_emails = self.cleaned_data.get("secondary_emails")
        if primary_email and secondary_emails:
            if primary_email in secondary_emails:
                msg = "Primary and secondary email address must be differents"
                self._errors["primary_email"] = self.error_class([msg])
        return self.cleaned_data

    def save(self):
        primary_email = self.cleaned_data.get("primary_email")
        secondary_emails = get_list(self.cleaned_data.get("secondary_emails"))

        primary_nominee = Nominee.objects.get(email__address=primary_email,
                                              nominee_position__nomcom=self.nomcom)
        secondary_nominees = Nominee.objects.filter(email__address__in=secondary_emails,
                                                    nominee_position__nomcom=self.nomcom)
        for nominee in secondary_nominees:
            # move nominations
            nominee.nomination_set.all().update(nominee=primary_nominee)
            # move feedback
            nominee.feedback_set.all().update(nominee=primary_nominee)
            # move nomineepositions
            for nominee_position in nominee.nomineeposition_set.all():
                primary_nominee_positions = NomineePosition.objects.filter(position=nominee_position.position,
                                                                           nominee=primary_nominee)
                primary_nominee_position = primary_nominee_positions and primary_nominee_positions[0] or None

                if primary_nominee_position:
                    # if already a nomineeposition object for a position and nominee,
                    # update the nomineepostion of primary nominee with the state and questionnaire
                    if nominee_position.time > primary_nominee_position.time:
                        primary_nominee_position.state = nominee_position.state
                        primary_nominee_position.save()
                    questionnaires = nominee_position.questionnaires.all()
                    if questionnaires:
                        primary_nominee_position.questionnaires.add(*questionnaires)

                else:
                    # It is not allowed two or more nomineeposition objects with same position and nominee
                    # move nominee_position object to primary nominee
                    nominee_position.nominee = primary_nominee
                    nominee_position.save()

            nominee.duplicated = primary_nominee
            nominee.save()

        secondary_nominees.update(duplicated=primary_nominee)


class NominateForm(BaseNomcomForm, forms.ModelForm):
    comments = forms.CharField(label='Comments', widget=forms.Textarea())

    fieldsets = [('Candidate Nomination', ('position', 'candidate_name',
                  'candidate_email', 'candidate_phone', 'comments'))]

    def __init__(self, *args, **kwargs):
        self.nomcom = kwargs.pop('nomcom', None)
        self.user = kwargs.pop('user', None)
        self.public = kwargs.pop('public', None)

        super(NominateForm, self).__init__(*args, **kwargs)
        if self.nomcom:
            self.fields['position'].queryset = Position.objects.filter(nomcom=self.nomcom)
        if not self.public:
            author = get_user_email(self.user)
            if author:
                self.fields['nominator_email'].initial = author.address
            self.fieldsets = [('Candidate Nomination', ('position',
                              'nominator_email', 'candidate_name',
                              'candidate_email', 'candidate_phone',
                              'comments'))]

    def save(self, commit=True):
        # Create nomination
        nomination = super(NominateForm, self).save(commit=False)
        nominator_email = self.cleaned_data.get('nominator_email', None)
        candidate_email = self.cleaned_data['candidate_email']
        candidate_name = self.cleaned_data['candidate_name']
        position = self.cleaned_data['position']
        comments = self.cleaned_data['comments']
        nomcom_template_path = '/nomcom/%s/' % self.nomcom.group.acronym
        nomcom_chair = self.nomcom.group.get_chair()
        nomcom_chair_mail = nomcom_chair and nomcom_chair.email.address or None

        # Create person and email if candidate email does't exist and send email
        email, created_email = Email.objects.get_or_create(address=candidate_email)
        if created_email:
            email.person = Person.objects.create(name=candidate_name,
                                                 ascii=unaccent.asciify(candidate_name),
                                                 address=candidate_email)
            email.save()

        # Add the nomination for a particular position
        nominee, created = Nominee.objects.get_or_create(email=email)
        nominee_position, nominee_position_created = NomineePosition.objects.get_or_create(position=position, nominee=nominee)

        # Complete nomination data
        feedback = Feedback.objects.create(position=position,
                                           nominee=nominee,
                                           comments=comments,
                                           type=FeedbackType.objects.get(slug='nomina'))
        author = None
        if self.public:
            author = get_user_email(self.user)
        else:
            if nominator_email:
                emails = Email.objects.filter(address=nominator_email)
                author = emails and emails[0] or None

        if author:
            nomination.nominator_email = author.address
            feedback.author = author
            feedback.save()

        nomination.nominee = nominee
        nomination.comments = feedback

        if commit:
            nomination.save()

        if created_email:
            # send email to secretariat and nomcomchair to warn about the new person
            subject = 'New person is created'
            from_email = settings.NOMCOM_FROM_EMAIL
            to_email = [settings.NOMCOM_ADMIN_EMAIL]
            context = {'email': email.address,
                       'fullname': email.person.name,
                       'person_id': email.person.id}
            path = nomcom_template_path + INEXISTENT_PERSON_TEMPLATE
            if nomcom_chair_mail:
                to_email.append(nomcom_chair_mail)
            send_mail(None, to_email, from_email, subject, path, context)

        # send email to nominee
        if nominee_position_created:
            subject = 'IETF Nomination Information'
            from_email = settings.NOMCOM_FROM_EMAIL
            to_email = email.address
            context = {'nominee': email.person.name,
                      'position': position}
            path = nomcom_template_path + NOMINEE_EMAIL_TEMPLATE
            send_mail(None, to_email, from_email, subject, path, context)

        # send email to nominee with questionnaire
        if nominee_position_created:
            if self.nomcom.send_questionnaire:
                subject = '%s Questionnaire' % position
                from_email = settings.NOMCOM_FROM_EMAIL
                to_email = email.address
                context = {'nominee': email.person.name,
                          'position': position}
                path = '%s%d/%s' % (nomcom_template_path,
                                    position.id, QUESTIONNAIRE_TEMPLATE)
                send_mail(None, to_email, from_email, subject, path, context)

        # send emails to nomcom chair
        subject = 'Nomination Information'
        from_email = settings.NOMCOM_FROM_EMAIL
        to_email = nomcom_chair_mail
        context = {'nominee': email.person.name,
                   'nominee_email': email.address,
                   'position': position}
        if author:
            context.update({'nominator': author.person.name,
                            'nominator_email': author.address})
        path = nomcom_template_path + NOMINATION_EMAIL_TEMPLATE
        send_mail(None, to_email, from_email, subject, path, context)

        return nomination

    class Meta:
        model = Nomination
        fields = ('position', 'nominator_email', 'candidate_name',
                  'candidate_email', 'candidate_phone')

    class Media:
        js = ("/js/jquery-1.5.1.min.js",
              "/js/nomcom.js", )


class NomComTemplateForm(BaseNomcomForm, DBTemplateForm):

    fieldsets = [('Template content', ('content', )),
                ]


class PositionForm(BaseNomcomForm, forms.ModelForm):

    fieldsets = [('Position', ('name', 'description',
                               'is_open', 'incumbent'))]

    class Meta:
        model = Position
        fields = ('name', 'description', 'is_open', 'incumbent')

    def __init__(self, *args, **kwargs):
        self.nomcom = kwargs.pop('nomcom', None)
        super(PositionForm, self).__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        self.instance.nomcom = self.nomcom
        super(PositionForm, self).save(*args, **kwargs)


class PrivateKeyForm(BaseNomcomForm, forms.Form):

    key = forms.CharField(label='Private key', widget=forms.Textarea(), required=False)

    fieldsets = [('Private key', ('key',))]
