from django import forms
from django.utils.translation import ugettext_lazy as _
from django.utils import six

import datetime
from collections import defaultdict

from .widgets import TimedeltaWidget
from .helpers import parse

class TimedeltaFormField(forms.Field):
    
    default_error_messages = {
        'invalid':_('Enter a valid time span: e.g. "3 days, 4 hours, 2 minutes"')
    }
    
    def __init__(self, *args, **kwargs):
        defaults = {'widget':TimedeltaWidget}
        defaults.update(kwargs)
        super(TimedeltaFormField, self).__init__(*args, **defaults)
        
    def clean(self, value):
        """
        This doesn't really need to be here: it should be tested in
        parse()...
        
        >>> t = TimedeltaFormField()
        >>> t.clean('1 day')
        datetime.timedelta(1)
        >>> t.clean('1 day, 0:00:00')
        datetime.timedelta(1)
        >>> t.clean('1 day, 8:42:42.342')
        datetime.timedelta(1, 31362, 342000)
        >>> t.clean('3 days, 8:42:42.342161')
        datetime.timedelta(3, 31362, 342161)
        >>> try:
        ...  t.clean('3 days, 8:42:42.3.42161')
        ... except forms.ValidationError as arg:
        ...  six.print_(arg.messages[0])
        Enter a valid time span: e.g. "3 days, 4 hours, 2 minutes"
        >>> t.clean('5 day, 8:42:42')
        datetime.timedelta(5, 31362)
        >>> t.clean('1 days')
        datetime.timedelta(1)
        >>> t.clean('1 second')
        datetime.timedelta(0, 1)
        >>> t.clean('1 sec')
        datetime.timedelta(0, 1)
        >>> t.clean('10 seconds')
        datetime.timedelta(0, 10)
        >>> t.clean('30 seconds')
        datetime.timedelta(0, 30)
        >>> t.clean('1 minute, 30 seconds')
        datetime.timedelta(0, 90)
        >>> t.clean('2.5 minutes')
        datetime.timedelta(0, 150)
        >>> t.clean('2 minutes, 30 seconds')
        datetime.timedelta(0, 150)
        >>> t.clean('.5 hours')
        datetime.timedelta(0, 1800)
        >>> t.clean('30 minutes')
        datetime.timedelta(0, 1800)
        >>> t.clean('1 hour')
        datetime.timedelta(0, 3600)
        >>> t.clean('5.5 hours')
        datetime.timedelta(0, 19800)
        >>> t.clean('1 day, 1 hour, 30 mins')
        datetime.timedelta(1, 5400)
        >>> t.clean('8 min')
        datetime.timedelta(0, 480)
        >>> t.clean('3 days, 12 hours')
        datetime.timedelta(3, 43200)
        >>> t.clean('3.5 day')
        datetime.timedelta(3, 43200)
        >>> t.clean('1 week')
        datetime.timedelta(7)
        >>> t.clean('2 weeks, 2 days')
        datetime.timedelta(16)
        >>> try:
        ...  t.clean(six.u('2 we\xe8k, 2 days'))
        ... except forms.ValidationError as arg:
        ...  six.print_(arg.messages[0])
        Enter a valid time span: e.g. "3 days, 4 hours, 2 minutes"
        """
        
        super(TimedeltaFormField, self).clean(value)
        if value == '' and not self.required:
            return ''
        try:
            return parse(value)
        except TypeError:
            raise forms.ValidationError(self.error_messages['invalid'])

class TimedeltaChoicesField(TimedeltaFormField):
    def __init__(self, *args, **kwargs):
        choices = kwargs.pop('choices')
        defaults = {'widget':forms.Select(choices=choices)}
        defaults.update(kwargs)
        super(TimedeltaChoicesField, self).__init__(*args, **defaults)
