from django import forms
from django.core.validators import validate_email

from models import *
from sec.utils.mail import MultiEmailField
from sec.utils.group import current_nomcom

from ietf.message.models import Message
from ietf.ietfauth.decorators import has_role
from ietf.wgchairs.accounts import get_person_for_user

# ---------------------------------------------
# Globals
# ---------------------------------------------

ANNOUNCE_FROM_GROUPS = ['ietf','rsoc','iab',current_nomcom().acronym]
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
             'The IAOC <bob.hinden@gmail.com>',
             'The IETF Trust <tme@multicasttech.com>',
             'RSOC Chair <rsoc-chair@iab.org>',
             'ISOC Board of Trustees <eburger@standardstrack.com>')
             
TO_LIST = ('IETF Announcement List <ietf-announce@ietf.org>',
           'I-D Announcement List <i-d-announce@ietf.org>',
           'The IESG <iesg@ietf.org>',
           'Working Group Chairs <wgchairs@ietf.org>',
           'BoF Chairs <bofchairs@ietf.org>',
           'Other...')
# ---------------------------------------------
# Custom Fields
# ---------------------------------------------

class MultiEmailField(forms.Field):
    def to_python(self, value):
        "Normalize data to a list of strings."

        # Return an empty list if no input was given.
        if not value:
            return []
        values = value.split(',')
        return [ x.strip() for x in values ]
        
    def validate(self, value):
        "Check if value consists only of valid emails."

        # Use the parent's handling of required fields, etc.
        super(MultiEmailField, self).validate(value)

        for email in value:
            validate_email(email)
            
# ---------------------------------------------
# Helper Functions
# ---------------------------------------------

def get_from_choices(user):
    '''
    This function returns a choices tuple containing
    all the Announced From choices.  Including
    leadership chairs and other entities.
    '''
    person = user.get_profile()
    if has_role(user,'Secretariat'):
        f = FROM_LIST
    elif has_role(user,'IETF Chair'):
        f = (FROM_LIST[2],FROM_LIST[5])
    elif has_role(user,'IAB Chair'):
        f = (FROM_LIST[6],)
    elif has_role(user,'IAD'):
        f = (FROM_LIST[9],)
    # NomCom, RSOC Chair, IAOC Chair aren't supported by has_role()
    elif Role.objects.filter(name="chair",
                             group__acronym__startswith="nomcom",
                             group__state="active",
                             group__type="ietf",
                             person=person):
        f = (FROM_LIST[7],)
    elif Role.objects.filter(person=person,
                             group__acronym='rsoc',
                             name="chair"):
        f = (FROM_LIST[13],)
    elif Role.objects.filter(person=person,
                             group__acronym='iaoc',
                             name="chair"):
        f = (FROM_LIST[11],)
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
#TO_CHOICES = tuple(AnnouncedTo.objects.values_list('announced_to_id','announced_to'))
TO_CHOICES = get_to_choices()
#FROM_CHOICES = get_from_choices()

# ---------------------------------------------
# Forms
# ---------------------------------------------

class AnnounceForm(forms.ModelForm):
    nomcom = forms.BooleanField(required=False)
    to_custom = MultiEmailField(required=False,label='')
    #cc = MultiEmailField(required=False)
    
    class Meta:
        model = Message
        fields = ('nomcom', 'to','to_custom','frm','cc','bcc','reply_to','subject','body')
        
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')
        super(AnnounceForm, self).__init__(*args, **kwargs)
        self.fields['to'].widget = forms.Select(choices=TO_CHOICES)
        self.fields['to'].help_text = 'Select name OR select Other... and enter email below'
        self.fields['frm'].widget = forms.Select(choices=get_from_choices(user))
        self.fields['frm'].label = 'From'
        self.fields['nomcom'].label = 'NomCom message?'
    
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
        message.by = get_person_for_user(user)
        if self.cleaned_data['to'] == 'Other...':
            message.to = self.cleaned_data['to_custom']
        if kwargs['commit']:
            message.save()
        
        # add nomcom to related groups if checked
        if self.cleaned_data.get('nomcom', False):
            nomcom = current_nomcom()
            message.related_groups.add(nomcom)
        
        return message
