# Copyright The IETF Trust 2020, All Rights Reserved
# -*- coding: utf-8 -*-

import datetime

from django.template import Library, Node, TemplateSyntaxError
from django.template.defaultfilters import date
from django.utils import timezone

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


class GetNowNode(Node):
    """Node that stores timezone.now() in a template variable"""
    def __init__(self, var_name):
        self.var_name = var_name

    def render(self, context):
        context[self.var_name] = timezone.now()
        return ''  # render nothing


@register.tag
def get_now(parser, token):
    """Get timezone.now() as a template variable"""
    toks = token.contents.split()  # split by spaces
    tag_name=toks[0]
    if len(toks) != 3 or toks[1].lower() != 'as':
        raise TemplateSyntaxError(f'{tag_name} tag requires "as <var>" argument')
    var_name = toks[2]
    return GetNowNode(var_name)
