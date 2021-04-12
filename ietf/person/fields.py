# Copyright The IETF Trust 2012-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import json

from collections import Counter
from urllib.parse import urlencode

from typing import Type # pyflakes:ignore

from django import forms
from django.core.validators import validate_email
from django.db import models # pyflakes:ignore
from django.urls import reverse as urlreverse
from django.utils.html import escape

import debug                            # pyflakes:ignore

from ietf.person.models import Email, Person
from ietf.utils.fields import SearchableField


def select2_id_name(objs):
    def format_email(e):
        return escape("%s <%s>" % (e.person.name, e.address))
    def format_person(p):
        if p.name_count > 1:
            return escape('%s (%s)' % (p.name,p.email().address if p.email() else 'no email address'))
        else:
            return escape(p.name)

    if objs and isinstance(objs[0], Email):
        formatter = format_email
    else:
        formatter = format_person
        c = Counter([p.name for p in objs])
        for p in objs:
           p.name_count = c[p.name]
        
    formatter = format_email if objs and isinstance(objs[0], Email) else format_person
    return [{ "id": o.pk, "text": formatter(o) } for o in objs if o]


def select2_id_name_json(objs):
    return json.dumps(select2_id_name(objs))


class SearchablePersonsField(SearchableField):
    """Server-based multi-select field for choosing
    persons/emails or just persons using select2.js.

    The field operates on either Email or Person models. In the case
    of Email models, the person name is shown next to the email
    address.

    The field uses a comma-separated list of primary keys in a
    CharField element as its API with some extra attributes used by
    the Javascript part.
    
    If the field will be programmatically updated, any model instances
    that may be added to the initial set should be included in the extra_prefetch
    list. These can then be added by updating val() and triggering the 'change'
    event on the select2 field in JavaScript.
    """
    model = Person # type: Type[models.Model]
    default_hint_text = "Type name to search for person."
    def __init__(self,
                 only_users=False, # only select persons who also have a user
                 all_emails=False, # select only active email addresses
                 extra_prefetch=None, # extra data records to include in prefetch
                 *args, **kwargs):
        super(SearchablePersonsField, self).__init__(*args, **kwargs)
        self.only_users = only_users
        self.all_emails = all_emails
        self.extra_prefetch = extra_prefetch or []
        assert all([isinstance(obj, self.model) for obj in self.extra_prefetch])

    def validate_pks(self, pks):
        """Validate format of PKs"""
        for pk in pks:
            if not pk.isdigit():
                raise forms.ValidationError("Unexpected value: %s" % pk)

    def make_select2_data(self, model_instances):
        # Include records needed by the initial value of the field plus any added 
        # via the extra_prefetch property.
        prefetch_set = set(model_instances).union(set(self.extra_prefetch))  # eliminate duplicates 
        return select2_id_name(list(prefetch_set))

    def ajax_url(self):
        url = urlreverse(
            "ietf.person.views.ajax_select2_search",
            kwargs={ "model_name": self.model.__name__.lower() }
        )
        query_args = {}
        if self.only_users:
            query_args["user"] = "1"
        if self.all_emails:
            query_args["a"] = "1"
        if len(query_args) > 0:
            url += '?%s' % urlencode(query_args)
        return url


class SearchablePersonField(SearchablePersonsField):
    """Version of SearchablePersonsField specialized to a single object."""
    max_entries = 1


class SearchableEmailsField(SearchablePersonsField):
    """Version of SearchablePersonsField with the defaults right for Emails."""
    model = Email # type: Type[models.Model]
    default_hint_text = "Type name or email to search for person and email address."

    def validate_pks(self, pks):
        for pk in pks:
            validate_email(pk)

    def get_model_instances(self, item_ids):
        return self.model.objects.filter(pk__in=item_ids).select_related("person")


class SearchableEmailField(SearchableEmailsField):
    """Version of SearchableEmailsField specialized to a single object."""
    max_entries = 1


class PersonEmailChoiceField(forms.ModelChoiceField):
    """ModelChoiceField targeting Email and displaying choices with the
    person name as well as the email address. Needs further
    restrictions, e.g. on role, to useful."""
    def __init__(self, *args, **kwargs):
        if not "queryset" in kwargs:
            kwargs["queryset"] = Email.objects.select_related("person")

        self.label_with = kwargs.pop("label_with", None)

        super(PersonEmailChoiceField, self).__init__(*args, **kwargs)

    def label_from_instance(self, email):
        if self.label_with == "person":
            return str(email.person)
        elif self.label_with == "email":
            return email.address
        else:
            return "{} <{}>".format(email.person, email.address)

