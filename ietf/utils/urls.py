# Copyright The IETF Trust 2016, All Rights Reserved

import six
import debug                            # pyflakes:ignore
from inspect import isclass

from django.conf.urls import url as django_url

def url(regex, view, kwargs=None, name=None):
    if name:
        branch = 'name'
    elif isinstance(view, (list, tuple)):
        branch = 'list'
    elif isinstance(view, six.string_types):
        branch = 'string'
        name = view
    elif callable(view) and hasattr(view, '__name__'):
        branch = 'callable'
        name = "%s.%s" % (view.__module__, view.__name__)
    elif isclass(view) or hasattr(view, '__class__'):
        branch = 'class'
    else:
        branch = 'notimpl'
        raise NotImplementedError("Auto-named url from view of type %s: %s" % (type(view), view))
    if name:
        branch = branch                 # silent pyflakes
        #debug.show('branch')
        #debug.show('name')
        pass
    return django_url(regex, view, kwargs=kwargs, name=name)
    