# Copyright The IETF Trust 2020, All Rights Reserved
# -*- coding: utf-8 -*-

import datetime

from django.template import Library
from django.template.defaultfilters import date

import debug                            # pyflakes:ignore

register = Library()

elide_timefmt = str.maketrans("aAefgGhHiIOPsTuZ:", "                 ")

@register.filter()
def dateformat(value, arg=None):
    """
    Formats a date or datetime according to the given format.
    Ignores the time-related format elements if a date is given.
    """
    if value in (None, ''):
        return ''
    if   isinstance(value, datetime.datetime):
        pass
    elif isinstance(value, datetime.date):
        arg = arg.translate(elide_timefmt).strip()
    return date(value, arg)
