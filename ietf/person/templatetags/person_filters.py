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
    