from django.utils import simplejson
from django.utils.html import escape
from django.utils.functional import lazy
from django import forms
from django.core.urlresolvers import reverse as urlreverse

import debug

from ietf.person.models import *

def json_emails(emails):
    if isinstance(emails, basestring):
        emails = Email.objects.filter(address__in=[x.strip() for x in emails.split(",") if x.strip()]).select_related("person")
    return simplejson.dumps([{"id": e.address + "", "name": escape(u"%s <%s>" % (e.person.name, e.address))} for e in emails])

class EmailsField(forms.CharField):
    def __init__(self, *args, **kwargs):
        kwargs["max_length"] = 1000
        if not "help_text" in kwargs:
            kwargs["help_text"] = "Type in name to search for person"
        super(EmailsField, self).__init__(*args, **kwargs)
        self.widget.attrs["class"] = "emails-field"
        self.widget.attrs["data-ajax-url"] = lazy(urlreverse, str)("ajax_search_emails") # make this lazy to prevent initialization problem

    def prepare_value(self, value):
        if not value:
            return ""
        if isinstance(value, str):
            return value
        return json_emails(value)

    def clean(self, value):
        value = super(EmailsField, self).clean(value)
        return Email.objects.filter(address__in=[x.strip() for x in value.split(",") if x.strip()]).select_related("person")

