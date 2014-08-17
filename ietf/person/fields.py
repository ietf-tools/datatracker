import json

from django.utils.html import escape
from django import forms
from django.core.urlresolvers import reverse as urlreverse

import debug                            # pyflakes:ignore

from ietf.person.models import Email

def json_emails(emails):
    if isinstance(emails, basestring):
        emails = Email.objects.filter(address__in=[x.strip() for x in emails.split(",") if x.strip()]).select_related("person")
    return json.dumps([{"id": e.address + "", "name": escape(u"%s <%s>" % (e.person.name, e.address))} for e in emails])

class EmailsField(forms.CharField):
    """Multi-select field using jquery.tokeninput.js. Since the API of
    tokeninput" is asymmetric, we have to pass it a JSON
    representation on the way out and parse the ids coming back as a
    comma-separated list on the way in."""

    def __init__(self, max_entries=None, hint_text="Type in name or email to search for person and email address", only_users=True,
                 *args, **kwargs):
        kwargs["max_length"] = 1000
        self.max_entries = max_entries
        self.only_users = only_users

        super(EmailsField, self).__init__(*args, **kwargs)

        self.widget.attrs["class"] = "tokenized-field"
        self.widget.attrs["data-hint-text"] = hint_text
        if self.max_entries != None:
            self.widget.attrs["data-max-entries"] = self.max_entries

    def parse_tokenized_value(self, value):
        return [x.strip() for x in value.split(",") if x.strip()]

    def prepare_value(self, value):
        if not value:
            value = ""
        if isinstance(value, basestring):
            addresses = self.parse_tokenized_value(value)
            value = Email.objects.filter(address__in=addresses).select_related("person")

        self.widget.attrs["data-pre"] = json_emails(value)
        # doing this in the constructor is difficult because the URL
        # patterns may not have been fully constructed there yet
        self.widget.attrs["data-ajax-url"] = urlreverse("ajax_search_emails")
        if self.only_users:
            self.widget.attrs["data-ajax-url"] += "?user=1" # require a Datatracker account

        return ",".join(e.address for e in value)

    def clean(self, value):
        value = super(EmailsField, self).clean(value)
        addresses = self.parse_tokenized_value(value)

        emails = Email.objects.filter(address__in=addresses).exclude(person=None).select_related("person")
        # there are still a couple of active roles without accounts so don't disallow those yet
        #if self.only_users:
        #    emails = emails.exclude(person__user=None)
        found_addresses = [e.address for e in emails]

        failed_addresses = [x for x in addresses if x not in found_addresses]
        if failed_addresses:
            raise forms.ValidationError(u"Could not recognize the following email addresses: %s. You can only input addresses already registered in the Datatracker." % ", ".join(failed_addresses))

        if self.max_entries != None and len(emails) > self.max_entries:
            raise forms.ValidationError(u"You can select at most %s entries only." % self.max_entries)

        return emails

