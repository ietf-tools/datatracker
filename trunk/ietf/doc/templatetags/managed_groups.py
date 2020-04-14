# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django import template

import debug                            # pyflakes:ignore

from ietf.group.models import Group
from ietf.group.utils import group_features_group_filter

register = template.Library()

@register.filter
def docman_groups(user):
    if not (user and hasattr(user, "is_authenticated") and user.is_authenticated):
        return []

    groups = Group.objects.filter(  role__person=user.person,
                                    type__features__has_documents=True,
                                    state__slug__in=('active', 'bof'))
    groups = group_features_group_filter(groups, user.person, 'docman_roles')
    return groups

@register.filter
def matman_groups(user):
    if not (user and hasattr(user, "is_authenticated") and user.is_authenticated):
        return []

    groups = Group.objects.filter(  role__person=user.person,
                                    type__features__has_session_materials=True,
                                    state__slug__in=('active', 'bof'))
    groups = group_features_group_filter(groups, user.person, 'matman_roles')
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

