# Copyright The IETF Trust 2021, All Rights Reserved
# -*- coding: utf-8 -*-

from django import template

import debug                            # pyflakes:ignore

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


@register.filter
def list_extract(items, arg):
    """Extract items from a list of containers

    Uses Django template lookup rules: tries list index / dict key lookup first, then
    tries to getattr. If the result is callable, calls with no arguments and uses the return
    value..

    Usage: {{ list_of_lists|list_extract:1 }} (gets elt 1 from each item in list)
           {{ list_of_dicts|list_extract:'key' }} (gets value of 'key' from each dict in list)
    """
    def _extract(item):
        try:
            return item[arg]
        except TypeError:
            pass
        attr = getattr(item, arg, None)
        return attr() if callable(attr) else attr

    return [_extract(item) for item in items]

@register.filter
def keep_only(items, arg):
    """Filter list of items based on an attribute

    Usage: {{ item_list|keep_only:'attribute' }}
      Returns the list, keeping only those whose where item[attribute] or item.attribute is
      present and truthy. The attribute can be an int or a string.
    """
    return [item for item, value in zip(items, list_extract(items, arg)) if value]
