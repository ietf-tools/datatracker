# Copyright The IETF Trust 2015-2020, All Rights Reserved
from django import template
from django.template.loader import render_to_string
from django.urls import reverse

from ietf.group.models import Group
from ietf.name.models import GroupTypeName

register = template.Library()

parents = GroupTypeName.objects.filter(slug__in=['ag','area','rag','team','dir','program'])

others = []
for group in Group.objects.filter(acronym__in=('rsoc',), state_id='active'):
    group.menu_url = reverse('ietf.group.views.group_home', kwargs=dict(acronym=group.acronym)) # type: ignore
    # could use group.about_url() instead
    others.append(group)

@register.simple_tag
def active_groups_menu():
    global parents, others
    for p in parents:
        p.menu_url = '/%s/'%p.slug
    return render_to_string('base/menu_active_groups.html', { 'parents': parents, 'others': others })

