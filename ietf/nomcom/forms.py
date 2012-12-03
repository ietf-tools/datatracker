from django import forms
from django.contrib.formtools.preview import FormPreview
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.core.urlresolvers import reverse
from django.conf import settings

from ietf.ietfauth.decorators import has_role
from ietf.utils import fields as custom_fields
from ietf.group.models import Group, Role
from ietf.name.models import RoleName
from ietf.person.models import Email


ROLODEX_URL = getattr(settings, 'ROLODEX_URL', None)


def get_group_or_404(year):
    return get_object_or_404(Group,
                             acronym__icontains=year,
                             state__slug='active',
                             nomcom__isnull=False)


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
