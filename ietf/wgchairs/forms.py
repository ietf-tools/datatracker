from django import forms
from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

from ietf.wgchairs.models import WGDelegate
from ietf.wgchairs.accounts import get_person_for_user
from ietf.idtracker.models import PersonOrOrgInfo


class RelatedWGForm(forms.Form):

    can_cancel = False

    def __init__(self, *args, **kwargs):
        self.wg = kwargs.pop('wg', None)
        self.user = kwargs.pop('user', None)
        self.message = {}
        super(RelatedWGForm, self).__init__(*args, **kwargs)

    def get_message(self):
        return self.message

    def set_message(self, msg_type, msg_value):
        self.message = {'type': msg_type,
                        'value': msg_value,
                       }


class RemoveDelegateForm(RelatedWGForm):

    delete = forms.MultipleChoiceField()

    def __init__(self, *args, **kwargs):
        super(RemoveDelegateForm, self).__init__(*args, **kwargs)
        self.fields['delete'].choices = [(i.pk, i.pk) for i in self.wg.wgdelegate_set.all()]

    def save(self):
        delegates = self.cleaned_data.get('delete')
        WGDelegate.objects.filter(pk__in=delegates).delete()
        self.set_message('success', 'Delegates removed')


class AddDelegateForm(RelatedWGForm):

    email = forms.EmailField()
    form_type = forms.CharField(widget=forms.HiddenInput, initial='single')

    def __init__(self, *args, **kwargs):
        super(AddDelegateForm, self).__init__(*args, **kwargs)
        self.next_form = self

    def get_next_form(self):
        return self.next_form

    def get_person(self, email):
        persons = PersonOrOrgInfo.objects.filter(emailaddress__address=email, iesglogin__isnull=False).distinct()
        if not persons:
            raise PersonOrOrgInfo.DoesNotExist
        if len(persons) > 1:
            raise PersonOrOrgInfo.MultipleObjectsReturned
        return persons[0]

    def save(self):
        email = self.cleaned_data.get('email')
        try:
            person = self.get_person(email)
        except PersonOrOrgInfo.DoesNotExist:
            self.next_form = NotExistDelegateForm(wg=self.wg, user=self.user, email=email)
            self.next_form.set_message('doesnotexist', 'There is no user with this email allowed to login to the system')
            return
        except PersonOrOrgInfo.MultipleObjectsReturned:
            self.next_form = MultipleDelegateForm(wg=self.wg, user=self.user, email=email)
            self.next_form.set_message('multiple', 'There are multiple users with this email in the system')
            return
        self.create_delegate(person)

    def create_delegate(self, person):
        (delegate, created) = WGDelegate.objects.get_or_create(wg=self.wg,
                                                               person=person)
        if not created:
            self.set_message('error', 'The email belongs to a person who is already a delegate')
        else:
            self.next_form = AddDelegateForm(wg=self.wg, user=self.user)
            self.next_form.set_message('success', 'A new delegate has been added')


class MultipleDelegateForm(AddDelegateForm):

    email = forms.EmailField(widget=forms.HiddenInput)
    form_type = forms.CharField(widget=forms.HiddenInput, initial='multiple')
    persons = forms.ChoiceField(widget=forms.RadioSelect, help_text='Please select one person from the list')
    submit_msg = 'Designate as delegate'

    def __init__(self, *args, **kwargs):
        self.email = kwargs.pop('email', None)
        super(MultipleDelegateForm, self).__init__(*args, **kwargs)
        if not self.email:
            self.email = self.data.get('email', None)
        self.fields['email'].initial = self.email
        self.fields['persons'].choices = [(i.pk, unicode(i)) for i in PersonOrOrgInfo.objects.filter(emailaddress__address=self.email, iesglogin__isnull=False).distinct().order_by('first_name')]

    def save(self):
        person_id = self.cleaned_data.get('persons')
        person = PersonOrOrgInfo.objects.get(pk=person_id)
        self.create_delegate(person)


class NotExistDelegateForm(MultipleDelegateForm):

    email = forms.EmailField(widget=forms.HiddenInput)
    form_type = forms.CharField(widget=forms.HiddenInput, initial='notexist')
    can_cancel = True
    submit_msg = 'Send email to these addresses'

    def __init__(self, *args, **kwargs):
        super(NotExistDelegateForm, self).__init__(*args, **kwargs)
        self.email_list = []
        del(self.fields['persons'])

    def get_email_list(self):
        if self.email_list:
            return self.email_list
        email_list = [self.email]
        email_list.append('IETF Secretariat <iesg-secretary@ietf.org>')
        email_list += ['%s <%s>' % i.person.email() for i in self.wg.wgchair_set.all() if i.person.email()]
        self.email_list = email_list
        return email_list

    def as_p(self):
        email_list = self.get_email_list()
        info = render_to_string('wgchairs/notexistdelegate.html', {'email_list': email_list})
        return info + super(NotExistDelegateForm, self).as_p()

    def send_email(self, email, template):
        subject = 'WG Delegate needs system credentials'
        persons = PersonOrOrgInfo.objects.filter(emailaddress__address=self.email).distinct()
        body = render_to_string(template,
                                {'chair': get_person_for_user(self.user),
                                 'delegate_email': self.email,
                                 'delegate_persons': persons,
                                 'wg': self.wg,
                                })
        mail = EmailMessage(subject=subject,
                            body=body,
                            to=email,
                            from_email=settings.DEFAULT_FROM_EMAIL)
        mail.send()


    def send_email_to_delegate(self, email):
        self.send_email(email, 'wgchairs/notexistsdelegate_delegate_email.txt')

    def send_email_to_secretariat(self, email):
        self.send_email(email, 'wgchairs/notexistsdelegate_secretariat_email.txt')

    def send_email_to_wgchairs(self, email):
        self.send_email(email, 'wgchairs/notexistsdelegate_wgchairs_email.txt')

    def save(self):
        self.next_form = AddDelegateForm(wg=self.wg, user=self.user)
        if settings.DEBUG:
            self.next_form.set_message('warning', 'Email was not sent cause tool is in DEBUG mode')
        else:
            email_list = self.get_email_list()
            self.send_email_to_delegate([email_list[0]])
            self.send_email_to_secretariat([email_list[1]])
            self.send_email_to_wgchairs(email_list[2:])
            self.next_form.set_message('success', 'Email sent successfully')


def add_form_factory(request, wg, user):
    if request.method != 'POST':
        return AddDelegateForm(wg=wg, user=user)

    if request.POST.get('form_type', None) == 'multiple':
        return MultipleDelegateForm(wg=wg, user=user, data=request.POST.copy())
    elif request.POST.get('form_type', None) == 'notexist':
        return NotExistDelegateForm(wg=wg, user=user, data=request.POST.copy())
    elif request.POST.get('form_type', None) == 'single':
        return AddDelegateForm(wg=wg, user=user, data=request.POST.copy())

    return AddDelegateForm(wg=wg, user=user)
