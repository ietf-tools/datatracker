import logging

from django import template
from django.middleware.csrf import get_token
from django.conf import settings
from django.core.files.storage import get_storage_class

staticfiles_storage = get_storage_class(settings.STATICFILES_STORAGE)()

register = template.Library()

log = logging.getLogger('dajaxice')


@register.simple_tag(takes_context=True)
def dajaxice_js_import(context, csrf=True):
    """ Return the js script tag for the dajaxice.core.js file
    If the csrf argument is present and it's ``nocsrf`` dajaxice will not
    try to mark the request as if it need the csrf token. By default use
    the dajaxice_js_import template tag will make django set the csrftoken
    cookie on the current request."""

    csrf = csrf != 'nocsrf'
    request = context.get('request')

    if request and csrf:
        get_token(request)
    elif csrf:
        log.warning("The 'request' object must be accesible within the "
                    "context. You must add 'django.contrib.messages.context"
                    "_processors.request' to your TEMPLATE_CONTEXT_PROCESSORS "
                    "and render your views using a RequestContext.")

    url = staticfiles_storage.url('dajaxice/dajaxice.core.js')
    return '<script src="%s" type="text/javascript" charset="utf-8"></script>' % url
