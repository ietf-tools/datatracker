# Copyright The IETF Trust 2016, All Rights Reserved

import six
import debug                            # pyflakes:ignore

from django.conf.urls import url as django_url

#@debug.trace
def url(regex, view, kwargs=None, name=None, prefix=''):
    if isinstance(view, (list, tuple)):
        pass                            # use the name passed in
    elif isinstance(view, six.string_types):
        name = view
    elif callable(view):
        name = "%s.%s" % (view.__module__, view.__name__)
    else:
        raise NotImplementedError("Auto-named url from view of type %s: %s" % (type(view), view))
    if name:
        debug.show('name')
    return django_url(regex, view, kwargs=kwargs, name=name, prefix=prefix)
    