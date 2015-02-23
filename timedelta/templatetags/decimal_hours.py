from django import template
register = template.Library()

from ..helpers import decimal_hours as dh

@register.filter(name='decimal_hours')
def decimal_hours(value, decimal_places=None):
    if value is None:
        return value
    return dh(value, decimal_places)
