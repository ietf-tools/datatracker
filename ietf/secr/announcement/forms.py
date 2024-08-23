# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django import forms

from ietf.group.models import Group, Role
from ietf.utils.html import unescape
from ietf.ietfauth.utils import has_role
from ietf.message.models import Message, AnnouncementFrom
from ietf.utils.fields import MultiEmailField

# ---------------------------------------------
# Globals
# ---------------------------------------------

TO_LIST = ('IETF Announcement List <ietf-announce@ietf.org>',
           'I-D Announcement List <i-d-announce@ietf.org>',
           'RFP Announcement List <rfp-announce@ietf.org>',
           'The IESG <iesg@ietf.org>',
           'Working Group Chairs <wgchairs@ietf.org>',
           'BOF Chairs <bofchairs@ietf.org>',
           'Other...')

# ---------------------------------------------
# Helper Functions
# ---------------------------------------------

def get_from_choices(user):
    '''
    This function returns a choices tuple containing
    all the Announced From choices.  Including
    leadership chairs and other entities.
    '''
    addresses = []
    if has_role(user,'Secretariat'):
        addresses = AnnouncementFrom.objects.values_list('address', flat=True).order_by('address').distinct()
    else:
        for role in user.person.role_set.all():
            addresses.extend(AnnouncementFrom.objects.filter(name=role.name, group=role.group).values_list('address', flat=True).order_by('address'))

    nomcom_choices = get_nomcom_choices(user)
    if nomcom_choices:
        addresses = list(addresses) + nomcom_choices

    choices = list(zip(addresses, addresses))
    if len(choices) > 1:
        choices.insert(0, ('', '(Choose an option)'))
    return choices


def get_nomcom_choices(user):
    '''
    Returns the list of nomcom email addresses for given user
    '''
    nomcoms = Role.objects.filter(name="chair",
                                  group__acronym__startswith="nomcom",
                                  group__state="active",
                                  group__type="nomcom",
                                  person=user.person)
    addresses = []
    for nomcom in nomcoms:
        year = nomcom.group.acronym[-4:]
        addresses.append('NomCom Chair %s <nomcom-chair-%s@ietf.org>' % (year,year))

    return addresses
        

def get_to_choices():
    return list(zip(TO_LIST,TO_LIST))


# ---------------------------------------------
# Forms
# ---------------------------------------------

class AnnounceForm(forms.ModelForm):
    nomcom = forms.ModelChoiceField(queryset=Group.objects.filter(acronym__startswith='nomcom',type='nomcom',state='active'),required=False)
    to_custom = MultiEmailField(required=False)

    class Meta:
        model = Message
        fields = ('nomcom', 'to','to_custom','frm','cc','bcc','reply_to','subject','body')

    def __init__(self, *args, **kwargs):
        if 'hidden' in kwargs:
            self.hidden = kwargs.pop('hidden')
        else:
            self.hidden = False
        user = kwargs.pop('user')
        person = user.person
        super(AnnounceForm, self).__init__(*args, **kwargs)
        self.fields['to'].widget = forms.Select(choices=get_to_choices())
        self.fields['to'].help_text = 'Select name OR select Other... and enter email below'
        self.fields['cc'].help_text = 'Use comma separated lists for emails (Cc, Bcc, Reply To)'
        self.fields['frm'].widget = forms.Select(choices=get_from_choices(user))
        self.fields['frm'].label = 'From'
        self.fields['reply_to'].required = True
        self.fields['nomcom'].label = 'NomCom message:'
        nomcom_roles = person.role_set.filter(group__in=self.fields['nomcom'].queryset,name='chair')
        secr_roles = person.role_set.filter(group__acronym='secretariat',name='secr')
        if nomcom_roles:
            self.initial['nomcom'] = nomcom_roles[0].group.pk
        if not nomcom_roles and not secr_roles:
            self.fields['nomcom'].widget = forms.HiddenInput()
        
        if self.hidden:
            for key in list(self.fields.keys()):
                self.fields[key].widget = forms.HiddenInput()

    def clean(self):
        super(AnnounceForm, self).clean()
        data = self.cleaned_data
        if self.errors:
            return self.cleaned_data
        if data['to'] == 'Other...' and not data['to_custom']:
            raise forms.ValidationError('You must enter a "To" email address')
        for k in ['to', 'frm', 'cc',]:
            data[k] = unescape(data[k])

        return data

    def save(self, *args, **kwargs):
        user = kwargs.pop('user')
        message = super(AnnounceForm, self).save(commit=False)
        message.by = user.person
        if self.cleaned_data['to'] == 'Other...':
            message.to = self.cleaned_data['to_custom']
        if kwargs['commit']:
            message.save()

        # handle nomcom message
        nomcom = self.cleaned_data.get('nomcom',False)
        if nomcom:
            message.related_groups.add(nomcom)

        return message