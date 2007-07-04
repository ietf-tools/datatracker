# Copyright The IETF Trust 2007, All Rights Reserved

from django import template
from ietf import __date__, __rev__, __version__, __id__


register = template.Library()


@register.simple_tag
def revision_time():
    return __date__[7:32]

@register.simple_tag
def revision_date():
    return __date__[34:-3]

@register.simple_tag
def revision_num():
    return __rev__[6:-2]

@register.simple_tag
def revision_id():
    return __id__[5:-2]

@register.simple_tag
def version_num():
    return __version__

