# Copyright The IETF Trust 2022, All Rights Reserved
# -*- coding: utf-8 -*-

"""Custom tags for the schedule editor"""

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def constraint_icon_for(constraint):
    # icons must be valid HTML
    icons = {
        'conflict': '<span class="encircled">{reversed}1</span>',
        'conflic2': '<span class="encircled">{reversed}2</span>',
        'conflic3': '<span class="encircled">{reversed}3</span>',
        'bethere': '<i class="bi bi-person"></i>{count}',
        'timerange': '<i class="bi bi-calendar"></i>',
        'time_relation': '&Delta;',
        'wg_adjacent': '{reversed}<i class="bi bi-skip-end"></i>',
        'chair_conflict': '{reversed}<i class="bi bi-person-circle"></i>',
        'tech_overlap': '{reversed}<i class="bi bi-link"></i>',
        'key_participant': '{reversed}<i class="bi bi-key"></i>',
    }
    return format_html(
        icons[constraint.name.slug],
        count=getattr(constraint, 'count', ''),
        reversed='-' if getattr(constraint, 'reversed', False) else '',
    )
