from django import template

from ietf.group.models import Group

register = template.Library()

@register.filter
def has_sessions(group,num):
    return group.session_set.filter(meeting__number=num).exists()

@register.filter
def active_roles(queryset):
    return queryset.filter(group__state_id__in=['active', 'bof']).exclude(group__acronym='secretariat')
    
@register.filter
def active_nomcoms(user):
    if not (user and hasattr(user, "is_authenticated") and user.is_authenticated):
        return []

    groups = []

    groups.extend(Group.objects.filter(
        role__person__user=user,
        type_id='nomcom',
        state__slug='active').distinct().select_related("type"))

    return groups

@register.inclusion_tag('person_link.html')
def person_link(linkee, **kwargs):
    title = ""
    if 'title' in kwargs:
        title = kwargs['title']
    if title == "Area Director":
        name = linkee.name
        plain_name = name
        email = linkee.email_address
    elif title == "Shepherd":
        name = linkee.person.name
        plain_name = name
        email = linkee
    else:
        name = linkee.person.name
        plain_name = linkee.person.plain_name
        email = linkee.email.address
    return {'name': name, 'plain_name': plain_name, 'email': email, 'title': title}
