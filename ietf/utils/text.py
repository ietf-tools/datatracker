from __future__ import unicode_literals

import re
import unicodedata

from django.utils.functional import allow_lazy
from django.utils import six
from django.utils.safestring import mark_safe

def xslugify(value):
    """
    Converts to ASCII. Converts spaces to hyphens. Removes characters that
    aren't alphanumerics, underscores, slash, or hyphens. Converts to
    lowercase.  Also strips leading and trailing whitespace.
    (I.e., does the same as slugify, but also converts slashes to dashes.)
    """
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub('[^\w\s/-]', '', value).strip().lower()
    return mark_safe(re.sub('[-\s/]+', '-', value))
xslugify = allow_lazy(xslugify, six.text_type)
