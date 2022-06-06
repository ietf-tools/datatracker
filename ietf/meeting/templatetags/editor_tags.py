# Copyright The IETF Trust 2022, All Rights Reserved
# -*- coding: utf-8 -*-

"""Custom tags for the schedule editor"""
import debug  # pyflakes: ignore

from django import template
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def constraint_icon_for(constraint_name, count=None):
    # icons must be valid HTML and kept up to date with tests.EditorTagTests.test_constraint_icon_for()
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
        'joint_with_groups': '<i class="bi bi-merge"></i>',
        'responsible_ad': '<span class="encircled">AD</span>',
    }
    reversed_suffix = '-reversed'
    if constraint_name.slug.endswith(reversed_suffix):
        reversed = True
        cn = constraint_name.slug[: -len(reversed_suffix)]
    else:
        reversed = False
        cn = constraint_name.slug
    return format_html(
        icons[cn],
        count=count or '',
        reversed='-' if reversed else '',
    )
