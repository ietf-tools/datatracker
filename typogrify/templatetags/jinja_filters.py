from typogrify.filters import amp, caps, initial_quotes, smartypants, titlecase, typogrify, widont, TypogrifyError
from functools import wraps
import jinja2
from jinja2.exceptions import TemplateError


def make_safe(f):
    """
    A function wrapper to make typogrify play nice with jinja2's
    unicode support.

    """
    @wraps(f)
    def wrapper(text):
        f.is_safe = True
        out = text
        try:
            out = f(text)
        except TypogrifyError as e:
            raise TemplateError(e.message)
        return jinja2.Markup(out)
    wrapper.is_safe = True
    return wrapper


def register(env):
    """
    Call this to register the template filters for jinj2.
    """
    env.filters['amp'] = make_safe(amp)
    env.filters['caps'] = make_safe(caps)
    env.filters['initial_quotes'] = make_safe(initial_quotes)
    env.filters['smartypants'] = make_safe(smartypants)
    env.filters['titlecase'] = make_safe(titlecase)
    env.filters['typogrify'] = make_safe(typogrify)
    env.filters['widont'] = make_safe(widont)
