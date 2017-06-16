import posixpath

from django.conf import settings

JQUERY_URL = getattr(
    settings, 'JQUERY_URL',
    'http://ajax.googleapis.com/ajax/libs/jquery/1.4/jquery.min.js')

if not ((':' in JQUERY_URL) or (JQUERY_URL.startswith('/'))):
    JQUERY_URL = posixpath.join(settings.MEDIA_URL, JQUERY_URL)

FORM_UTILS_MEDIA_URL = getattr(settings, 'FORM_UTILS_MEDIA_URL', settings.MEDIA_URL)
