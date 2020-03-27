# Copyright The IETF Trust 2020, All Rights Reserved


from django import template
import debug                            # pyflakes:ignore

register = template.Library()

@register.filter
def classname(obj):
    return obj.__class__.__name__
