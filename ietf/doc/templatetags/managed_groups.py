from django import template

from ietf.group.models import Group, Role

register = template.Library()

@register.filter
def managed_groups(user):
    if not (user and hasattr(user, "is_authenticated") and user.is_authenticated):
        return []

    groups = [ g for g in Group.objects.filter(
                                role__person__user=user,
                                type__features__has_session_materials=True,
                                state__slug__in=('active', 'bof')).select_related("type")
                 if Role.objects.filter(group=g, person__user=user, name__slug__in=g.type.features.matman_roles) ]

    return groups

@register.filter
def managed_review_groups(user):
    if not (user and hasattr(user, "is_authenticated") and user.is_authenticated):
        return []

    groups = []

    groups.extend(Group.objects.filter(
        role__name__slug='secr',
        role__person__user=user,
        reviewteamsettings__isnull=False,
        state__slug='active').select_related("type"))

    return groups

