# Copyright The IETF Trust 2017-2020, All Rights Reserved
# -*- coding: utf-8 -*-

from django.template.library import Library

from ietf.utils.markdown import markdown as utils_markdown

register = Library()


@register.filter(name="markdown", is_safe=True)
def markdown(string):
    # One issue is that the string is enclosed in <p></p>... Let's remove the leading/trailing ones...
    return utils_markdown(string)[3:-4]

