# Copyright The IETF Trust 2017-2020, All Rights Reserved
# -*- coding: utf-8 -*-

import re

from django.template.library import Library
from django.template.defaultfilters import stringfilter

from ietf.utils.html import remove_tags
from ietf.utils.markdown import markdown as utils_markdown

register = Library()


@register.filter(is_safe=True)
@stringfilter
def removetags(value, tags):
    """Removes a comma-separated list of [X]HTML tags from the output."""
    return remove_tags(value, re.split(r"\s*,\s*", tags))

@register.filter(name="markdown", is_safe=True)
def markdown(string):
    # One issue is that the string is enclosed in <p></p>... Let's remove the leading/trailing ones...
    return utils_markdown(string)[3:-4]

