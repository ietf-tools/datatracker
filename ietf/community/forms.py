import hashlib
import datetime

from django import forms
from django.conf import settings
from django.contrib.sites.models import Site

from ietf.utils.mail import send_mail
from ietf.community.models import Rule, DisplayConfiguration, RuleManager
from ietf.community.display import DisplayField


class RuleForm(forms.ModelForm):

    class Meta:
        model = Rule
        fields = ('rule_type', 'value')

    def __init__(self, *args, **kwargs):
        self.clist = kwargs.pop('clist', None)
        super(RuleForm, self).__init__(*args, **kwargs)

    def save(self):
        self.instance.community_list = self.clist
        super(RuleForm, self).save()

    def get_all_options(self):
        result = []
        for i in RuleManager.__subclasses__():
            options = i(None).options()
            if options:
                result.append({'type': i.codename,
                               'options': options})
        return result
        

class DisplayForm(forms.ModelForm):

    class Meta:
        model = DisplayConfiguration
        fields = ('sort_method', )

    def save(self):
        data = self.data
        fields = []
        for i in DisplayField.__subclasses__():
            if data.get(i.codename, None):
                fields.append(i.codename)
        self.instance.display_fields = ','.join(fields)
        super(DisplayForm, self).save()


class SubscribeForm(forms.Form):

    email = forms.EmailField("Your email")

    def __init__(self, *args, **kwargs):
        self.clist = kwargs.pop('clist')
        self.significant = kwargs.pop('significant')
        super(SubscribeForm, self).__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        self.send_email()
        return True

    def send_email(self):
        domain = Site.objects.get_current().domain
        today = datetime.date.today().strftime('%Y%m%d')
        subject = 'Confirm list subscription: %s' % self.clist
        from_email = settings.DEFAULT_FROM_EMAIL
        to_email = self.cleaned_data['email']
        auth = hashlib.md5('%s%s%s%s%s' % (settings.SECRET_KEY, today, to_email, 'subscribe', self.significant)).hexdigest()
        context = {
            'domain': domain,
            'clist': self.clist,
            'today': today,
            'auth': auth,
            'to_email': to_email,
            'significant': self.significant,
        }
        send_mail(None, to_email, from_email, subject, 'community/public/subscribe_email.txt', context)


class UnSubscribeForm(SubscribeForm):

    def send_email(self):
        domain = Site.objects.get_current().domain
        today = datetime.date.today().strftime('%Y%m%d')
        subject = 'Confirm list subscription cancelation: %s' % self.clist
        from_email = settings.DEFAULT_FROM_EMAIL
        to_email = self.cleaned_data['email']
        auth = hashlib.md5('%s%s%s%s%s' % (settings.SECRET_KEY, today, to_email, 'unsubscribe', self.significant)).hexdigest()
        context = {
            'domain': domain,
            'clist': self.clist,
            'today': today,
            'auth': auth,
            'to_email': to_email,
            'significant': self.significant,
        }
        send_mail(None, to_email, from_email, subject, 'community/public/unsubscribe_email.txt', context)
