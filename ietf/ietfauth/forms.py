import datetime
import hashlib
import subprocess

from django import forms
from django.forms import ModelForm
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.utils.translation import ugettext_lazy as _

from ietf.utils.mail import send_mail
from ietf.person.models import Person, Email


class RegistrationForm(forms.Form):

    email = forms.EmailField(label="Your email")
    realm = 'IETF'
    expire = 3

    def save(self, *args, **kwargs):
        # why is there a save when it doesn't save?
        self.send_email()
        return True

    def send_email(self):
        domain = Site.objects.get_current().domain
        subject = 'Confirm registration at %s' % domain
        from_email = settings.DEFAULT_FROM_EMAIL
        to_email = self.cleaned_data['email']
        today = datetime.date.today().strftime('%Y%m%d')
        auth = hashlib.md5('%s%s%s%s' % (settings.SECRET_KEY, today, to_email, self.realm)).hexdigest()
        context = {
            'domain': domain,
            'today': today,
            'realm': self.realm,
            'auth': auth,
            'username': to_email,
            'expire': settings.DAYS_TO_EXPIRE_REGISTRATION_LINK,
        }
        send_mail(self.request, to_email, from_email, subject, 'registration/creation_email.txt', context)

    def clean_email(self):
        email = self.cleaned_data.get('email', '')
        if not email:
            return email
        if User.objects.filter(username=email).count():
            raise forms.ValidationError(_('An account with the email address you provided already exists.'))
        return email


class RecoverPasswordForm(RegistrationForm):

    realm = 'IETF'

    def send_email(self):
        domain = Site.objects.get_current().domain
        subject = 'Password reset at %s' % domain
        from_email = settings.DEFAULT_FROM_EMAIL
        today = datetime.date.today().strftime('%Y%m%d')
        to_email = self.cleaned_data['email']
        today = datetime.date.today().strftime('%Y%m%d')
        auth = hashlib.md5('%s%s%s%s' % (settings.SECRET_KEY, today, to_email, self.realm)).hexdigest()
        context = {
            'domain': domain,
            'today': today,
            'realm': self.realm,
            'auth': auth,
            'username': to_email,
            'expire': settings.DAYS_TO_EXPIRE_REGISTRATION_LINK,
        }
        send_mail(self.request, to_email, from_email, subject, 'registration/password_reset_email.txt', context)

    def clean_email(self):
        email = self.cleaned_data.get('email', '')
        return email


class PasswordForm(forms.Form):

    password1 = forms.CharField(label=_("Password"), widget=forms.PasswordInput)
    password2 = forms.CharField(label=_("Password confirmation"), widget=forms.PasswordInput,
        help_text=_("Enter the same password as above, for verification."))

    def __init__(self, *args, **kwargs):
        self.username = kwargs.pop('username')
        self.update_user = User.objects.filter(username=self.username).count() > 0
        super(PasswordForm, self).__init__(*args, **kwargs)

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1", "")
        password2 = self.cleaned_data["password2"]
        if password1 != password2:
            raise forms.ValidationError(_("The two password fields didn't match."))
        return password2

    def get_password(self):
        return self.cleaned_data.get('password1')

    def create_user(self):
        user = User.objects.create(username=self.username,
                                   email=self.username)
        email = Email.objects.filter(address=self.username)
        person = None
        if email.count():
            email = email[0]
            if email.person:
                person = email.person
        else:
            email = None
        if not person:
            person = Person.objects.create(user=user,
                                           name=self.username,
                                           ascii=self.username)
        if not email:
            email = Email.objects.create(address=self.username,
                                         person=person)
        email.person = person
        email.save()
        person.user = user
        person.save()
        return user

    def get_user(self):
        return User.objects.get(username=self.username)

    def save_password_file(self):
        if getattr(settings, 'USE_PYTHON_HTDIGEST', None):
            pass_file = settings.HTPASSWD_FILE
            realm = settings.HTDIGEST_REALM
            password = self.get_password()
            username = self.username
            prefix = '%s:%s:' % (username, realm)
            key = hashlib.md5(prefix + password).hexdigest()
            f = open(pass_file, 'r+')
            pos = f.tell()
            line = f.readline()
            while line:
                if line.startswith(prefix):
                    break
                pos=f.tell()
                line = f.readline()
            f.seek(pos)
            f.write('%s%s\n' % (prefix, key))
            f.close()
        else:
            p = subprocess.Popen([settings.HTPASSWD_COMMAND, "-b", settings.HTPASSWD_FILE, self.username, self.get_password()], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = p.communicate()

    def save(self):
        if self.update_user:
            user = self.get_user()
        else:
            user = self.create_user()
        user.set_password(self.get_password())
        user.save()
        self.save_password_file()
        return user

class TestEmailForm(forms.Form):
    email = forms.EmailField(required=False)

class PersonForm(ModelForm):
    request = None
    new_emails = []
    class Meta:
        from ietf.person.models import Person
        model = Person
        exclude = ('time','user')

    def confirm_address(self,email):
        person = self.instance
        domain = Site.objects.get_current().domain
        user = person.user
        if len(email) == 0:
            return
        subject = 'Confirm email address for %s' % person.name
        from_email = settings.DEFAULT_FROM_EMAIL
        to_email = email
        today = datetime.date.today().strftime('%Y%m%d')
        auth = hashlib.md5('%s%s%s%s' % (settings.SECRET_KEY, today, to_email, user)).hexdigest()
        context = {
            'today': today,
            'domain': domain,
            'user': user,
            'email': email,
            'expire': settings.DAYS_TO_EXPIRE_REGISTRATION_LINK,
            'auth': auth,
        }
        send_mail(self.request, to_email, from_email, subject, 'registration/add_email_email.txt', context)

    def save(self, force_insert=False, force_update=False, commit=True):
        from ietf.group.models import Role 
        from ietf.person.models import Alias
        m = super(PersonForm, self).save(commit=False)
        self.new_emails = [v for k,v in self.data.items() if k[:10] == u'new_email_' and u'@' in v]

        for email in self.new_emails:
            self.confirm_address(email)

        # Process email active flags
        emails = Email.objects.filter(person=self.instance)
        for email in emails:
            email.active = self.data.__contains__(email.address)
            if commit:
                email.save()

        # Process email for roles
        for k,v in self.data.items():
            if k[:11] == u'role_email_':
                role = Role.objects.get(id=k[11:])
                email = Email.objects.get(address = v)
                role.email = email
                if commit:
                    role.save()

        # Make sure the alias table contains any new and/or old names.
        old_names = set([x.name for x in Alias.objects.filter(person=self.instance)])
        curr_names = set([x for x in [self.instance.name, 
                 self.instance.ascii,
                 self.instance.ascii_short,
                 self.data['name'],
                 self.data['ascii'],
                 self.data['ascii_short']] if len(x)])
        new_names = curr_names - old_names
        for name in new_names:
            alias = Alias(person=self.instance,name=name)
            if commit:
                alias.save()

        if commit:
            m.save()
        return m

