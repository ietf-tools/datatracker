# Copyright The IETF Trust 2017-2020, All Rights Reserved

import datetime

from django import template

import debug  # pyflakes:ignore

from ietf.nomcom.utils import is_eligible
from ietf.person.models import Alias

register = template.Library()


@register.filter
def is_nomcom_eligible(person, date=datetime.date.today()):
    return is_eligible(person=person, date=date)


@register.filter
def person_by_name(name):
    "Look up a person record from name"
    if not isinstance(name, (type(b""), type(""))):
        return None
    alias = Alias.objects.filter(name=name).first()
    return alias.person if alias else None


# CLEANUP: There are several hundred Person objects with no Alias object,
# violating the expectations of the code. The check for the existence of an
# alias object below matching the person's name avoids presenting a link that
# we know will 404. When the database is corrected and we can expect that the
# Alias for the person's name to always be there, we can remove this extra
# database query (or leave it as a safeguard until it becomes a performance
# issue.)


@register.inclusion_tag("person/person_link.html")
def person_link(person, **kwargs):
    """Render a link to a Person

    If person is None or a string, renders as a span containing '(None)'.
    """
    if isinstance(person, str):
        # If person is a string, most likely an invalid template variable was referenced.
        # That normally comes in as an empty string, but may be non-empty if string_if_invalid
        # is set. Translate strings into None to try to get consistent behavior.
        person = None
    title = kwargs.get("title", "")
    cls = kwargs.get("class", "")
    with_email = kwargs.get("with_email", True)
    if person is not None:
        plain_name = person.plain_name()
        name = (
            person.name
            if person.alias_set.filter(name=person.name).exists()
            else plain_name
        )
        email = person.email_address()
        return {
            "name": name,
            "plain_name": plain_name,
            "email": email,
            "title": title,
            "class": cls,
            "with_email": with_email,
        }
    else:
        return {}


@register.inclusion_tag("person/person_link.html")
def email_person_link(email, **kwargs):
    title = kwargs.get("title", "")
    cls = kwargs.get("class", "")
    with_email = kwargs.get("with_email", True)
    plain_name = email.person.plain_name()
    name = (
        email.person.name
        if email.person.alias_set.filter(name=email.person.name).exists()
        else plain_name
    )
    email = email.address
    return {
        "name": name,
        "plain_name": plain_name,
        "email": email,
        "title": title,
        "class": cls,
        "with_email": with_email,
    }