from django.conf import settings
from django import forms
from idtracker.models import PersonOrOrgInfo
from django.db.models import Q
from django.template.loader import render_to_string
from django.core.mail import EmailMessage


class ManagingShepherdForm(forms.Form):
    email = forms.EmailField(required=False)
    is_assign_current = forms.BooleanField(required=False)
    
    
    def __init__(self, *args, **kwargs):
        if kwargs.has_key('current_person'):
            self.current_person = kwargs.pop('current_person')            
        return super(ManagingShepherdForm, self).__init__(*args, **kwargs)
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email:
            return None
        
        try:
            PersonOrOrgInfo.objects. \
                  filter(emailaddress__type__in=[ "INET", "Prim",], 
                        emailaddress__address=email) \
                        [:1].get()
        except PersonOrOrgInfo.DoesNotExist:
            if self.cleaned_data.get('is_assign_current'):
                self._send_email(email)
            raise forms.ValidationError("Person with such email does not exist")
        return email
    
    def clean(self):
        if self.cleaned_data.get('email') and \
                                    self.cleaned_data.get('is_assign_current'):
            raise forms.ValidationError("You should choose to assign to current \
                        person or input the email. Not both at te same time. ")
        
        return self.cleaned_data
    
    def change_shepherd(self, document, save=True):
        email = self.cleaned_data.get('email')        
        if email:
            person = PersonOrOrgInfo.objects. \
                  filter(emailaddress__type__in=[ "INET", "Prim",], 
                        emailaddress__address=email) \
                        [:1].get()
        else:
            person = self.current_person        
        document.shepherd = person 
        if save: 
            document.save()
        return document
    
    def _send_email(self, email, 
                        template='idrfc/edit_management_shepherd_email.txt'):
        subject = 'WG Delegate needs system credentials'        
        body = render_to_string(template,
                                {'email': email,
                                })
        mail = EmailMessage(subject=subject,
                            body=body,
                            to=[email, settings.DEFAULT_FROM_EMAIL, ],
                            from_email=settings.DEFAULT_FROM_EMAIL)
        mail.send()