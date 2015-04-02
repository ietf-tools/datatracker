from django import template
register = template.Library()

# Don't really like using relative imports, but no choice here!
from ..helpers import parse, nice_repr, iso8601_repr, total_seconds as _total_seconds


@register.filter(name='timedelta')
def timedelta(value, display="long"):
    if value is None:
        return value
    if isinstance(value, basestring):
        value = parse(value)
    return nice_repr(value, display)


@register.filter(name='iso8601')
def iso8601(value):
    return timedelta(value, display='iso8601')


@register.filter(name='total_seconds')
def total_seconds(value):
    if value is None:
        return value
    return _total_seconds(value)


@register.filter(name='total_seconds_sort')
def total_seconds(value, places=10):
    if value is None:
        return value
    return ("%0" + str(places) + "i") % _total_seconds(value)

