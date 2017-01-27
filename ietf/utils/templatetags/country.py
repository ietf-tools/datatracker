from django.template.base import Library
from django.template.defaultfilters import stringfilter

from django_countries import countries

register = Library()

@register.filter(is_safe=True)
@stringfilter
def country_name(value):
    """
    Converts country code to country name
    """
    return dict(countries).get(value, "")
