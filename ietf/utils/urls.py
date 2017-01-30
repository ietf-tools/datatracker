# Copyright The IETF Trust 2016, All Rights Reserved

import six
import debug                            # pyflakes:ignore
from inspect import isclass

from django.conf.urls import url as django_url

def url(regex, view, kwargs=None, name=None, prefix=''):
    if isinstance(view, (list, tuple)):
        pass                            # use the name passed in
    elif isinstance(view, six.string_types):
        name = view
    elif isclass(view) or hasattr(view, '__class__'):
        pass
    elif callable(view) and hasattr(view, '__name__'):
        if str(view.__module__).startswith('django.'):
            pass
        else:
            name = "%s.%s" % (view.__module__, view.__name__)
    else:
        raise NotImplementedError("Auto-named url from view of type %s: %s" % (type(view), view))
    if name:
        #debug.show('name')
        pass
    return django_url(regex, view, kwargs=kwargs, name=name, prefix=prefix)
    