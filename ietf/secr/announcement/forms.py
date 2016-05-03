from django import forms

from ietf.group.models import Group, Role
from ietf.ietfauth.utils import has_role
from ietf.message.models import Message
from ietf.secr.utils.group import current_nomcom
from ietf.utils.fields import MultiEmailField

# ---------------------------------------------
# Globals
# ---------------------------------------------

ANNOUNCE_FROM_GROUPS = ['ietf','rsoc','iab']
if current_nomcom():
    ANNOUNCE_FROM_GROUPS += [ current_nomcom().acronym ]
ANNOUNCE_TO_GROUPS= ['ietf']

# this list isn't currently available as a Role query so it's hardcoded
FROM_LIST = ('IETF Secretariat <ietf-secretariat@ietf.org>',
             'IESG Secretary <iesg-secretary@ietf.org>',
             'The IESG <iesg@ietf.org>',
             'Internet-Drafts Administrator <internet-drafts@ietf.org>',
             'IETF Agenda <agenda@ietf.org>',
             'IETF Chair <chair@ietf.org>',
             'IAB Chair <iab-chair@ietf.org> ',
             'NomCom Chair <nomcom-chair@ietf.org>',
             'IETF Registrar <ietf-registrar@ietf.org>',
             'IETF Administrative Director <iad@ietf.org>',
             'IETF Executive Director <exec-director@ietf.org>',
             'The IAOC <ldaigle@thinkingcat.com>',
             'The IETF Trust <ietf-trust@ietf.org>',
             'RSOC Chair <rsoc-chair@iab.org>',
             'ISOC Board of Trustees <bob.hinden@gmail.com>',
             'RFC Series Editor <rse@rfc-editor.org>',
             'IAB Executive Administrative Manager <execd@iab.org>',
             'IETF Mentoring Program <mentoring@ietf.org>',
             'ISOC CEO <ceo@isoc.org>')

TO_LIST = ('IETF Announcement List <ietf-announce@ietf.org>',
           'I-D Announcement List <i-d-announce@ietf.org>',
           'The IESG <iesg@ietf.org>',
           'Working Group Chairs <wgchairs@ietf.org>',
           'BoF Chairs <bofchairs@ietf.org>',
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
    person = user.person
    f = []
    if has_role(user,'Secretariat'):
        f = FROM_LIST
    elif has_role(user,'IETF Chair'):
        f = (FROM_LIST[2],FROM_LIST[5])
    elif has_role(user,'IAB Chair'):
        f = (FROM_LIST[6],)
    elif has_role(user,'IAD'):
        f = (FROM_LIST[9],FROM_LIST[12],FROM_LIST[18],FROM_LIST[11],)
    #RSOC Chair, IAOC Chair aren't supported by has_role()
    elif Role.objects.filter(person=person,
                             group__acronym='rsoc',
                             name="chair"):
        f = (FROM_LIST[13],)
    elif Role.objects.filter(person=person,
                             group__acronym='iaoc',
                             name="chair"):
        f = (FROM_LIST[11],)
    elif Role.objects.filter(person=person,
                             group__acronym='rse',
                             name="chair"):
        f = (FROM_LIST[15],)
    elif Role.objects.filter(person=person,
                             group__acronym='iab',
                             name='execdir'):
        f = (FROM_LIST[6],FROM_LIST[16])
    elif Role.objects.filter(person=person,
                             group__acronym='mentor',
                             name="chair"):
        f = (FROM_LIST[17],)
    elif Role.objects.filter(person=person,
                             group__acronym='isoc',
                             name="ceo"):
        f = (FROM_LIST[18],)
    elif Role.objects.filter(person=person,
                             group__acronym='isocbot',
                             name="chair"):
        f = (FROM_LIST[14],)
    elif Role.objects.filter(person=person,
                             group__acronym='ietf-trust',
                             name="chair"):
        f = (FROM_LIST[12],)

    # NomCom
    nomcoms = Role.objects.filter(name="chair",
                                  group__acronym__startswith="nomcom",
                                  group__state="active",
                                  group__type="nomcom",
                                  person=person)
    if nomcoms:
        year = nomcoms[0].group.acronym[-4:]
        alias = 'NomCom Chair %s <nomcom-chair-%s@ietf.org>' % (year,year)
        f = (alias,)

    return zip(f,f)

def get_to_choices():
    #groups = Group.objects.filter(acronym__in=ANNOUNCE_TO_GROUPS)
    #roles = Role.objects.filter(group__in=(groups),name="Announce")
    #choices = [ (r.email, r.person.name) for r in roles ]
    #choices.append(('Other...','Other...'),)
    return zip(TO_LIST,TO_LIST)

# ---------------------------------------------
# Select Choices
# ---------------------------------------------
TO_CHOICES = get_to_choices()
#FROM_CHOICES = get_from_choices()

# ---------------------------------------------
# Forms
# ---------------------------------------------

class AnnounceForm(forms.ModelForm):
    #nomcom = forms.BooleanField(required=False)
    nomcom = forms.ModelChoiceField(queryset=Group.objects.filter(acronym__startswith='nomcom',type='nomcom',state='active'),required=False)
    to_custom = MultiEmailField(required=False,label='')
    #cc = MultiEmailField(required=False)

    class Meta:
        model = Message
        fields = ('nomcom', 'to','to_custom','frm','cc','bcc','reply_to','subject','body')

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')
        person = user.person
        super(AnnounceForm, self).__init__(*args, **kwargs)
        self.fields['to'].widget = forms.Select(choices=TO_CHOICES)
        self.fields['to'].help_text = 'Select name OR select Other... and enter email below'
        self.fields['cc'].help_text = 'Use comma separated lists for emails (Cc, Bcc, Reply To)'
        self.fields['frm'].widget = forms.Select(choices=get_from_choices(user))
        self.fields['frm'].label = 'From'
        self.fields['nomcom'].label = 'NomCom message:'
        nomcom_roles = person.role_set.filter(group__in=self.fields['nomcom'].queryset,name='chair')
        secr_roles = person.role_set.filter(group__acronym='secretariat',name='secr')
        if nomcom_roles:
            self.initial['nomcom'] = nomcom_roles[0].group.pk
        if not nomcom_roles and not secr_roles:
            self.fields['nomcom'].widget = forms.HiddenInput()
        self.initial['reply_to'] = 'ietf@ietf.org'

    def clean(self):
        super(AnnounceForm, self).clean()
        data = self.cleaned_data
        if self.errors:
            return self.cleaned_data
        if data['to'] == 'Other...' and not data['to_custom']:
            raise forms.ValidationError('You must enter a "To" email address')

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
