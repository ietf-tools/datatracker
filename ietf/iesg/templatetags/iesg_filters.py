from django import template

from ietf.iesg.utils import telechat_page_count as page_counter

register = template.Library()

@register.filter
def telechat_page_count(telechat):
    return page_counter(telechat['date']).for_approval
