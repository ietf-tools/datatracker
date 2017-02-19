# Copyright the IETF Trust 2017, All Rights Reserved

from __future__ import unicode_literals

from django.template.library import Library
from django.template.defaultfilters import stringfilter

from ietf.utils.html import remove_tags

register = Library()

@register.filter(is_safe=True)
@stringfilter
def removetags(value, tags):
    """Removes a space separated list of [X]HTML tags from the output."""
    return remove_tags(value, tags)

