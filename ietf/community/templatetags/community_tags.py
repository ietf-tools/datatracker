from django import template
from django.template.loader import render_to_string
from django.conf import settings

from ietf.community.models import CommunityList
from ietf.group.models import Role


register = template.Library()

@register.assignment_tag
def get_user_managed_lists(user):
    if not (user and hasattr(user, "is_authenticated") and user.is_authenticated()):
        return ''
    lists = {'personal': CommunityList.objects.get_or_create(user=user)[0]}
    try:
        person = user.person
        groups = []
        managed_areas = [i.group for i in Role.objects.filter(name__slug='ad', email__in=person.email_set.all())]
        for area in managed_areas:
            groups.append(CommunityList.objects.get_or_create(group=area)[0])
        managed_wg = [i.group for i in Role.objects.filter(name__slug='chair', group__type__slug='wg', email__in=person.email_set.all())]
        for wg in managed_wg:
            groups.append(CommunityList.objects.get_or_create(group=wg)[0])
        lists['group'] = groups
    except:
        pass
    return lists

@register.inclusion_tag('community/display_field.html', takes_context=False)
def show_field(field, doc):
    return {'field': field,
            'value': field.get_value(doc),
           }


@register.simple_tag
def get_clist_view(clist):
    if settings.DEBUG or not clist.cached:
        clist.cached = render_to_string('community/raw_view.html', {
                'cl': clist,
                'dc': clist.get_display_config()
            })
        clist.save()
        return clist.cached
