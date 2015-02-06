from typogrify.filters import amp, caps, initial_quotes, smartypants, titlecase, typogrify, widont, TypogrifyError
from functools import wraps
from django.conf import settings
from django import template
from django.utils.safestring import mark_safe
from django.utils.encoding import force_str


register = template.Library()


def make_safe(f):
    """
    A function wrapper to make typogrify play nice with django's
    unicode support.

    """
    @wraps(f)
    def wrapper(text):
        text = force_str(text)
        f.is_safe = True
        out = text
        try:
            out = f(text)
        except TypogrifyError as e:
            if settings.DEBUG:
                raise e
            return text
        return mark_safe(out)
    wrapper.is_safe = True
    return wrapper


register.filter('amp', make_safe(amp))
register.filter('caps', make_safe(caps))
register.filter('initial_quotes', make_safe(initial_quotes))
register.filter('smartypants', make_safe(smartypants))
register.filter('titlecase', make_safe(titlecase))
register.filter('typogrify', make_safe(typogrify))
register.filter('widont', make_safe(widont))
