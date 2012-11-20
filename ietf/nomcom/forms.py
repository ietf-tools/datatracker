from django import forms
from django.contrib.formtools.preview import FormPreview
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.core.urlresolvers import reverse

from ietf.ietfauth.decorators import has_role
from ietf.utils import fields as custom_fields
from ietf.group.models import Group, Role
from ietf.name.models import RoleName
from ietf.person.models import Email


class ManageGroupForm(forms.Form):

    chair = forms.EmailField(label="Chair email", required=False,
                             widget=forms.TextInput(attrs={'size': '40'}))
    members = custom_fields.MultiEmailField(label="Members email", required=False)

    def __init__(self, *args, **kwargs):
        super(ManageGroupForm, self).__init__(*args, **kwargs)


class ManageGroupFormPreview(FormPreview):
    form_template = 'nomcom/manage_group.html'
    preview_template = 'nomcom/manage_group_review.html'

    def preview_get(self, request):
        if not has_role(request.user, "Secretariat"):
            return HttpResponseForbidden("Must be a secretariat")

        return super(ManageGroupFormPreview, self).preview_get(request)


    def parse_params(self, *args, **kwargs):
        group_acronym = kwargs['acronym']
        group = Group.objects.get(acronym=group_acronym)
        chairs = group.role_set.filter(name__slug='chair')
        members = group.role_set.filter(name__slug='member')
        if chairs:
            self.form.base_fields['chair'].initial = chairs[0].email.address
        if members:
            self.form.base_fields['members'].initial = ',\r\n'.join([role.email.address for role in members])
        self.state['group'] = group

    def process_preview(self, request, form, context):
        chair_email = form.cleaned_data['chair']
        members_email = form.cleaned_data['members'].replace('\r\n', '').replace(' ', '').split(',')
        members_info = []
        emails_not_found = []
        try:
            chair_email_obj = Email.objects.get(address=chair_email)
            chair_person = chair_email_obj.person
        except Email.DoesNotExist:
            chair_person = None
            chair_email_obj = None
        chair_info = {'email': chair_email,
                      'email_obj': chair_email_obj,
                      'person': chair_person}

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
        self.state.update({'chair_info': chair_info,
                           'members_info': members_info,
                           'emails_not_found': emails_not_found})

    def done(self, request, cleaned_data):
        group = self.state['group']
        chair_info = self.state['chair_info']
        members_info = self.state['members_info']
        members_email = [member['email'] for member in self.state['members_info']]
        members_excluded = group.role_set.filter(name__slug='member').exclude(email__address__in=members_email)
        members_excluded.delete()
        for member in members_info:
            Role.objects.get_or_create(name=RoleName.objects.get(slug="member"),
                                       group=group,
                                       person=member['person'],
                                       email=member['email_obj'])

        chair_exclude = group.role_set.filter(name__slug='chair').exclude(email__address=chair_info['email'])
        chair_exclude.delete()
        if chair_info['email_obj'] and chair_info['person']:
            Role.objects.get_or_create(name=RoleName.objects.get(slug="chair"),
                                      group=group,
                                      person=chair_info['person'],
                                      email=chair_info['email_obj'])

        return HttpResponseRedirect(reverse('manage_group', kwargs={'acronym': group.acronym}))
