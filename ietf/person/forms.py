import json

from django.utils.html import escape
from django.utils.functional import lazy
from django import forms
from django.core.urlresolvers import reverse as urlreverse

import debug

from ietf.person.models import *

def json_emails(emails):
    if isinstance(emails, basestring):
        emails = Email.objects.filter(address__in=[x.strip() for x in emails.split(",") if x.strip()]).select_related("person")
    return json.dumps([{"id": e.address + "", "name": escape(u"%s <%s>" % (e.person.name, e.address))} for e in emails])

class EmailsField(forms.CharField):
    """Multi-select field using jquery.tokeninput.js. Since the API of
    tokeninput" is asymmetric, we have to pass it a JSON
    representation on the way out and parse the ids coming back as a
    comma-separated list on the way in."""

    def __init__(self, *args, **kwargs):
        kwargs["max_length"] = 1000
        if not "help_text" in kwargs:
            kwargs["help_text"] = "Type in name to search for person"
        super(EmailsField, self).__init__(*args, **kwargs)
        self.widget.attrs["class"] = "tokenized-field"
        self.widget.attrs["data-ajax-url"] = lazy(urlreverse, str)("ajax_search_emails") # make this lazy to prevent initialization problem

    def parse_tokenized_value(self, value):
        return Email.objects.filter(address__in=[x.strip() for x in value.split(",") if x.strip()]).select_related("person")

    def prepare_value(self, value):
        if not value:
            return ""
        if isinstance(value, str) or isinstance(value, unicode):
            value = self.parse_tokenized_value(value)
        return json_emails(value)

    def clean(self, value):
        value = super(EmailsField, self).clean(value)
        return self.parse_tokenized_value(value)

