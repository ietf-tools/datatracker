# Copyright The IETF Trust 2022, All Rights Reserved
# -*- coding: utf-8 -*-

"""Custom tags for the schedule editor"""

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def constraint_icon_for(constraint):
    if constraint.name.slug == 'bethere':
        # special case because it uses an attr that is sometimes added to the constraint
        icon = format_html('<i class="bi bi-person"></i>{}', getattr(constraint, 'count', ''))
    else:
        # icons must be valid HTML
        icons = {
            'conflict': '<span class="encircled">1</span>',
            'conflic2': '<span class="encircled">2</span>',
            'conflic3': '<span class="encircled">3</span>',
            'timerange': '<i class="bi bi-calendar"></i>',
            'time_relation': '&Delta;',
            'wg_adjacent': '<i class="bi bi-skip-end"></i>',
            'chair_conflict': '<i class="bi bi-person-circle"></i>',
            'tech_overlap': '<i class="bi bi-link"></i>',
            'key_participant': '<i class="bi bi-key"></i>',
        }
        icon = mark_safe(icons[constraint.name.slug])
    return icon
