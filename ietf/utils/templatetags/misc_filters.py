# Copyright The IETF Trust 2021, All Rights Reserved
# -*- coding: utf-8 -*-

from django import template


register = template.Library()


@register.filter
def merge_media(forms, arg=None):
    """Merge media for a list of forms
    
    Usage: {{ form_list|merge_media }}
      * With no arg, returns all media from all forms with duplicates removed
    
    Usage: {{ form_list|merge_media:'media_type' }}
      * With an arg, returns only media of that type. Types 'css' and 'js' are common.
        See Django documentation for more information about form media.
    """
    if len(forms) == 0:
        return ''
    combined = forms[0].media
    if len(forms) > 1:
        for val in forms[1:]:
            combined += val.media
    if arg is None:
        return str(combined)
    return str(combined[arg])
