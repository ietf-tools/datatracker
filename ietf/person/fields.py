import json

from django.utils.html import escape
from django import forms
from django.core.urlresolvers import reverse as urlreverse

import debug                            # pyflakes:ignore

from ietf.person.models import Email, Person

def tokeninput_id_name_json(objs):
    def format_email(e):
        return escape(u"%s <%s>" % (e.person.name, e.address))
    def format_person(p):
        return escape(p.name)

    formatter = format_email if objs and isinstance(objs[0], Email) else format_person

    return json.dumps([{ "id": o.pk, "name": formatter(o) } for o in objs])

class AutocompletedPersonsField(forms.CharField):
    """Tokenizing autocompleted multi-select field for choosing
    persons/emails or just persons using jquery.tokeninput.js.

    The field operates on either Email or Person models. In the case
    of Email models, the person name is shown next to the email address.

    The field uses a comma-separated list of primary keys in a
    CharField element as its API, the tokeninput Javascript adds some
    selection magic on top of this so we have to pass it a JSON
    representation of ids and user-understandable labels."""

    def __init__(self,
                 max_entries=None, # max number of selected objs
                 only_users=False, # only select persons who also have a user
                 model=Person, # or Email
                 hint_text="Type in name to search for person",
                 *args, **kwargs):
        kwargs["max_length"] = 1000
        self.max_entries = max_entries
        self.only_users = only_users
        self.model = model

        super(AutocompletedPersonsField, self).__init__(*args, **kwargs)

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
            pks = self.parse_tokenized_value(value)
            value = self.model.objects.filter(pk__in=pks).select_related("person")
        if isinstance(value, self.model):
            value = [value]

        self.widget.attrs["data-pre"] = tokeninput_id_name_json(value)

        # doing this in the constructor is difficult because the URL
        # patterns may not have been fully constructed there yet
        self.widget.attrs["data-ajax-url"] = urlreverse("ajax_tokeninput_search", kwargs={ "model_name": self.model.__name__.lower() })
        if self.only_users:
            self.widget.attrs["data-ajax-url"] += "?user=1" # require a Datatracker account

        return ",".join(e.address for e in value)

    def clean(self, value):
        value = super(AutocompletedPersonsField, self).clean(value)
        pks = self.parse_tokenized_value(value)

        objs = self.model.objects.filter(pk__in=pks)
        if self.model == Email:
            objs = objs.exclude(person=None).select_related("person")

            # there are still a couple of active roles without accounts so don't disallow those yet
            #if self.only_users:
            #    objs = objs.exclude(person__user=None)

        found_pks = [str(o.pk) for o in objs]
        failed_pks = [x for x in pks if x not in found_pks]
        if failed_pks:
            raise forms.ValidationError(u"Could not recognize the following {model_name}s: {pks}. You can only input {model_name}s already registered in the Datatracker.".format(pks=", ".join(failed_pks), model_name=self.model.__name__.lower()))

        if self.max_entries != None and len(objs) > self.max_entries:
            raise forms.ValidationError(u"You can select at most %s entries only." % self.max_entries)

        return objs

class AutocompletedPersonField(AutocompletedPersonsField):
    """Version of AutocompletedPersonsField specialized to a single object."""

    def __init__(self, *args, **kwargs):
        kwargs["max_entries"] = 1
        super(AutocompletedPersonField, self).__init__(*args, **kwargs)

    def clean(self, value):
        return super(AutocompletedPersonField, self).clean(value).first()


class AutocompletedEmailsField(AutocompletedPersonsField):
    """Version of AutocompletedPersonsField with the defaults right for Emails."""

    def __init__(self, model=Email, hint_text="Type in name or email to search for person and email address",
                 *args, **kwargs):
        super(AutocompletedEmailsField, self).__init__(model=model, hint_text=hint_text, *args, **kwargs)

class AutocompletedEmailField(AutocompletedEmailsField):
    """Version of AutocompletedEmailsField specialized to a single object."""

    def __init__(self, *args, **kwargs):
        kwargs["max_entries"] = 1
        super(AutocompletedEmailField, self).__init__(*args, **kwargs)

    def clean(self, value):
        return super(AutocompletedEmailField, self).clean(value).first()


