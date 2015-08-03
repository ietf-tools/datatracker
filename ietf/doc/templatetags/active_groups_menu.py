from django import template
from django.template.loader import render_to_string

from ietf.name.models import GroupTypeName

register = template.Library()

@register.simple_tag
def active_groups_menu():
    parents = GroupTypeName.objects.filter(slug__in=['ag','area','team','dir'])
    for p in parents:
        p.menu_url = '/%s/'%p.slug
    return render_to_string('base/menu_active_groups.html', { 'parents': parents })

