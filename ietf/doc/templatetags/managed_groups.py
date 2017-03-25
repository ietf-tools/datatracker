from django import template

from ietf.group.models import Group

register = template.Library()

@register.filter
def managed_groups(user):
    if not (user and hasattr(user, "is_authenticated") and user.is_authenticated):
        return []

    groups = []
    # groups.extend(Group.objects.filter(
    #     role__name__slug='ad',
    #     role__person__user=user,
    #     type__slug='area',
    #     state__slug='active').select_related("type"))

    groups.extend(Group.objects.filter(
        role__name__slug='chair',
        role__person__user=user,
        type__slug__in=('rg', 'wg', 'ag'),
        state__slug__in=('active', 'bof')).select_related("type"))

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

