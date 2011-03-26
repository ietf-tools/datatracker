from django.utils.functional import lazy
from django.core.urlresolvers import reverse

"""
A lazily evaluated version of `reverse()`_.

It is useful for when you need to use a URL reversal before Django's
URL names map is loaded. Some common cases where this method is necessary are:

    * in your URL configuration (such as the ``url`` argument for the
      ``django.views.generic.simple.redirect_to`` generic view).

    * providing a reversed URL to a decorator (such as the ``login_url`` argument
      for the ``django.contrib.auth.decorators.permission_required`` decorator).

Usually unicode would be preference but str is the right type instead of unicode.
This is because reverse passes through iri_to_uri which converts it to a string 
"""

reverse_lazy = lazy(reverse, str)
