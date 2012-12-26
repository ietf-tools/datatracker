from django.conf import settings
from django import forms
from django.contrib.formtools.preview import FormPreview
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.core.urlresolvers import reverse

from ietf.utils import unaccent
from ietf.utils.mail import send_mail
from ietf.ietfauth.decorators import has_role
from ietf.utils import fields as custom_fields
from ietf.group.models import Group, Role
from ietf.name.models import RoleName, FeedbackType
from ietf.person.models import Email, Person
from ietf.nomcom.models import NomCom, Nomination, Nominee, NomineePosition, \
                               Position, Feedback
from ietf.nomcom.utils import QUESTIONNAIRE_TEMPLATE, NOMINATION_EMAIL_TEMPLATE, \
                              INEXISTENT_PERSON_TEMPLATE, NOMINEE_EMAIL_TEMPLATE

ROLODEX_URL = getattr(settings, 'ROLODEX_URL', None)


def get_group_or_404(year):
    return get_object_or_404(Group,
                             acronym__icontains=year,
                             state__slug='active',
                             nomcom__isnull=False)


class BaseNomcomForm(forms.ModelForm):
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


class EditMembersForm(forms.Form):

    members = custom_fields.MultiEmailField(label="Members email", required=False)


class EditMembersFormPreview(FormPreview):
    form_template = 'nomcom/edit_members.html'
    preview_template = 'nomcom/edit_members_preview.html'

    def __call__(self, request, *args, **kwargs):
        year = kwargs['year']
        group = get_group_or_404(year)
        is_group_chair = group.is_chair(request.user)
        is_secretariat = has_role(request.user, "Secretariat")
        if not is_secretariat and not is_group_chair:
            return HttpResponseForbidden("Must be a secretariat or group chair")

        self.state['group'] = group
        self.state['rolodex_url'] = ROLODEX_URL
        self.group = group
        self.year = year

        return super(EditMembersFormPreview, self).__call__(request, *args, **kwargs)

    def parse_params(self, *args, **kwargs):
        members = self.group.role_set.filter(name__slug='member')

        if members:
            self.form.base_fields['members'].initial = ',\r\n'.join([role.email.address for role in members])

    def process_preview(self, request, form, context):
        members_email = form.cleaned_data['members'].replace('\r\n', '').replace(' ', '').split(',')

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

        return HttpResponseRedirect(reverse('edit_members', kwargs={'year': self.year}))


class EditChairForm(forms.Form):

    chair = forms.EmailField(label="Chair email", required=False,
                             widget=forms.TextInput(attrs={'size': '40'}))


class EditChairFormPreview(FormPreview):
    form_template = 'nomcom/edit_chair.html'
    preview_template = 'nomcom/edit_chair_preview.html'

    def __call__(self, request, *args, **kwargs):
        year = kwargs['year']
        group = get_group_or_404(year)
        is_secretariat = has_role(request.user, "Secretariat")
        if not is_secretariat:
            return HttpResponseForbidden("Must be a secretariat")

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

        return HttpResponseRedirect(reverse('edit_chair', kwargs={'year': self.year}))


class EditPublicKeyForm(forms.ModelForm):
    class Meta:
        model = NomCom
        fields = ('public_key',)


class NominateForm(BaseNomcomForm):
    comments = forms.CharField(label='Comments', widget=forms.Textarea())

    fieldsets = [('Candidate Nomination', ('position', 'candidate_name', 'candidate_email', 'candidate_phone', 'comments'))]

    def __init__(self, *args, **kwargs):
        self.nomcom = kwargs.pop('nomcom', None)
        self.user = kwargs.pop('user', None)
        super(NominateForm, self).__init__(*args, **kwargs)
        if self.nomcom:
            self.fields['position'].queryset = Position.objects.filter(nomcom=self.nomcom)

    def save(self, commit=True):
        # Create nomination
        nomination = super(NominateForm, self).save(commit=False)
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
        author_emails = Email.objects.filter(person__user=self.user)
        author = author_emails and author_emails[0] or None
        feedback = Feedback.objects.create(position=position,
                                           nominee=nominee,
                                           comments=comments,
                                           type=FeedbackType.objects.get(slug='nomina'))
        if author:
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
                path = '%s%d/%s' % (nomcom_template_path, position.id, QUESTIONNAIRE_TEMPLATE)
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
        fields = ('position', 'candidate_name', 'candidate_email', 'candidate_phone')
