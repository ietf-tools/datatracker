# Copyright The IETF Trust 2017-2020, All Rights Reserved

import datetime

from django import template

import debug                            # pyflakes:ignore

from ietf.meeting.utils import is_nomcom_eligible as util_is_nomcom_eligible
from ietf.person.models import Alias

register = template.Library()

@register.filter
def is_nomcom_eligible(person, date=datetime.date.today()):
    return util_is_nomcom_eligible(person,date)

@register.filter
def person_by_name(name):
    "Look up a person record from name"
    if not isinstance(name, (type(b''), type(u''))):
        return None
    alias = Alias.objects.filter(name=name).first()
    return alias.person if alias else None

@register.inclusion_tag('person/person_link.html')
def person_link(person, **kwargs):
    title = kwargs.get('title', '')
    cls = kwargs.get('class', '')
    name = person.name
    plain_name = person.plain_name()
    email = person.email_address()
    return {'name': name, 'plain_name': plain_name, 'email': email, 'title': title, 'class': cls}


@register.inclusion_tag('person/person_link.html')
def email_person_link(email, **kwargs):
    title = kwargs.get('title', '')
    cls = kwargs.get('class', '')
    name = email.person.name
    plain_name = email.person.plain_name()
    email = email.address
    return {'name': name, 'plain_name': plain_name, 'email': email, 'title': title, 'class': cls}
