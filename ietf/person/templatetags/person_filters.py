# Copyright The IETF Trust 2007, All Rights Reserved

import datetime

from django import template

import debug                            # pyflakes:ignore

from ietf.meeting.utils import is_nomcom_eligible as util_is_nomcom_eligible

register = template.Library()

@register.filter
def is_nomcom_eligible(person, date=datetime.date.today()):
    return util_is_nomcom_eligible(person,date)

