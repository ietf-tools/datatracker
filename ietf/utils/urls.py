# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import debug  # pyflakes:ignore

from inspect import isclass

from django.urls import re_path
from django.utils.encoding import force_str
from django.views.generic import View


def url(regex, view, kwargs=None, name=None):
    if hasattr(view, "view_class"):
        view_name = "%s.%s" % (view.__module__, view.view_class.__name__)
    elif callable(view) and hasattr(view, "__name__"):
        view_name = "%s.%s" % (view.__module__, view.__name__)
    else:
        view_name = regex

    if name:
        branch = "name"
    elif isinstance(view, (list, tuple)):
        branch = "list"
    elif isinstance(view, (str, bytes)):
        branch = "string"
        name = force_str(view)
    elif callable(view) and hasattr(view, "__name__"):
        branch = "callable"
        name = view_name
    elif isinstance(view, View):
        branch = "view"
    elif isclass(view) or hasattr(view, "__class__"):
        branch = "class"
    else:
        branch = "notimpl"
        raise NotImplementedError(
            "Auto-named url from view of type %s: %s" % (type(view), view)
        )
    if branch == "name":
        # List explicit url names with accompanying view dotted-path:
        # debug.say("%s %s" % (view_name, name))
        pass
    if name:
        branch = branch  # silent pyflakes
        # debug.show('branch')
        # debug.show('name')
        pass
    return re_path(regex, view, kwargs=kwargs, name=name)
